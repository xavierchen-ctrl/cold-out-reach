"""Scheduled email sending — create, list, process."""
import json
import base64
from datetime import datetime
from utils import now_tw
from typing import List, Optional
from uuid import UUID

from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, Lead, LeadActivity, ActivityType, ScheduledEmail, EmailOpen
from routers.tracking import TRACKING_BASE_URL

router = APIRouter(prefix="/api/emails", tags=["email_scheduler"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    lead_id: UUID
    template_id: Optional[UUID] = None
    to_email: str
    subject: str
    body: str
    scheduled_at: datetime  # ISO string from frontend


class ScheduledEmailOut(BaseModel):
    id: UUID
    lead_id: UUID
    template_id: Optional[UUID]
    to_email: str
    subject: str
    body: str
    scheduled_at: datetime
    sent_at: Optional[datetime]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/schedule", response_model=ScheduledEmailOut)
def schedule_email(
    body: ScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Inject tracking pixel
    email_id = str(body.lead_id) + "_" + now_tw().strftime("%Y%m%d%H%M%S")
    tracking_pixel = f'<img src="{TRACKING_BASE_URL}/api/track/open/{email_id}" width="1" height="1" style="display:none" />'
    tracked_body = body.body + "\n\n" + tracking_pixel

    sched = ScheduledEmail(
        lead_id=body.lead_id,
        template_id=body.template_id,
        to_email=body.to_email,
        subject="[WAVENET] " + body.subject if not body.subject.startswith("[WAVENET]") else body.subject,
        body=tracked_body,
        scheduled_at=body.scheduled_at,
        created_by=current_user.id,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.get("/scheduled", response_model=List[ScheduledEmailOut])
def list_scheduled(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ScheduledEmail).filter(ScheduledEmail.status == "pending")
    if current_user.role == "sales":
        q = q.filter(ScheduledEmail.created_by == current_user.id)
    return q.order_by(ScheduledEmail.scheduled_at).all()


@router.post("/process_scheduled")
def process_scheduled(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process all due scheduled emails. Requires Gmail token on the creator."""
    now = now_tw()
    due = db.query(ScheduledEmail).filter(
        ScheduledEmail.status == "pending",
        ScheduledEmail.scheduled_at <= now,
    ).all()

    sent_count = 0
    failed_count = 0

    for sched in due:
        creator = db.query(User).filter(User.id == sched.created_by).first()
        if not creator or not creator.gmail_token:
            sched.status = "failed"
            db.commit()
            failed_count += 1
            continue

        try:
            import google.oauth2.credentials as google_creds
            from googleapiclient.discovery import build

            token_data = json.loads(creator.gmail_token)
            creds = google_creds.Credentials(
                token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
            )
            service = build("gmail", "v1", credentials=creds)
            msg = MIMEText(sched.body, "html", "utf-8")
            msg["To"] = sched.to_email
            msg["Subject"] = sched.subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            sched.status = "sent"
            sched.sent_at = now_tw()

            # Log activity
            activity = LeadActivity(
                lead_id=sched.lead_id,
                type=ActivityType.email_sent,
                content=f"[排程發信] To: {sched.to_email}\nSubject: {sched.subject}",
                created_by=sched.created_by or current_user.id,
            )
            db.add(activity)
            db.commit()
            sent_count += 1
        except Exception as e:
            sched.status = "failed"
            db.commit()
            failed_count += 1

    return {"sent": sent_count, "failed": failed_count}


@router.get("/open_status/{lead_id}")
def get_open_status(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get email open events for a lead."""
    opens = db.query(EmailOpen).filter(EmailOpen.lead_id == lead_id).order_by(EmailOpen.opened_at.desc()).all()
    return [{"email_id": o.email_id, "opened_at": o.opened_at.isoformat(), "ip": o.ip} for o in opens]
