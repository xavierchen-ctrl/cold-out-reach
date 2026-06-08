import json
import os
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from utils import now_tw
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import google.generativeai as genai

from database import get_db
from models import (
    Lead, User, UserRole, EmailSequence, SequenceEnrollment,
    PendingEmail, LeadActivity, ActivityType
)
from auth import get_current_user

router = APIRouter(prefix="/api/sequences", tags=["sequences"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

TEMPLATES = {
    "intro": "初次開發信。專業友善，簡介數位行銷服務，邀請 15 分鐘通話。",
    "followup": "追蹤跟進信。溫和提醒，不施壓，強調具體價值。",
    "proposal": "報價提案信。提出具體方案，邀請進一步討論。",
}


class SequenceStep(BaseModel):
    day: int
    template_type: str  # intro / followup / proposal


class SequenceCreate(BaseModel):
    name: str
    steps: List[SequenceStep]


class SequenceOut(BaseModel):
    id: UUID
    name: str
    steps: List[SequenceStep]
    created_at: datetime
    enrollment_count: int = 0

    class Config:
        from_attributes = True


class EnrollRequest(BaseModel):
    lead_ids: List[UUID]


class PendingEmailOut(BaseModel):
    id: UUID
    lead_id: UUID
    company_name: str
    to_email: str
    subject: str
    body: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[SequenceOut])
def list_sequences(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seqs = db.query(EmailSequence).all()
    result = []
    for s in seqs:
        steps = json.loads(s.steps)
        count = db.query(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == s.id,
            SequenceEnrollment.status == "active"
        ).count()
        result.append(SequenceOut(
            id=s.id, name=s.name,
            steps=[SequenceStep(**st) for st in steps],
            created_at=s.created_at,
            enrollment_count=count,
        ))
    return result


@router.post("", response_model=SequenceOut)
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seq = EmailSequence(
        name=body.name,
        steps=json.dumps([s.model_dump() for s in body.steps]),
        created_by=current_user.id,
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    return SequenceOut(
        id=seq.id, name=seq.name,
        steps=body.steps,
        created_at=seq.created_at,
        enrollment_count=0,
    )


@router.delete("/{seq_id}")
def delete_sequence(seq_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seq = db.query(EmailSequence).filter(EmailSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    db.delete(seq)
    db.commit()
    return {"message": "deleted"}


@router.post("/{seq_id}/enroll")
def enroll_leads(
    seq_id: UUID,
    body: EnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seq = db.query(EmailSequence).filter(EmailSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    steps = json.loads(seq.steps)
    first_day = steps[0]["day"] if steps else 1
    enrolled = 0
    skipped = 0

    for lead_id in body.lead_ids:
        # check already enrolled
        existing = db.query(SequenceEnrollment).filter(
            SequenceEnrollment.lead_id == lead_id,
            SequenceEnrollment.sequence_id == seq_id,
            SequenceEnrollment.status == "active",
        ).first()
        if existing:
            skipped += 1
            continue
        enrollment = SequenceEnrollment(
            lead_id=lead_id,
            sequence_id=seq_id,
            current_step=0,
            next_send_at=now_tw() + timedelta(days=first_day),
            enrolled_by=current_user.id,
        )
        db.add(enrollment)
        enrolled += 1

    db.commit()
    return {"enrolled": enrolled, "skipped": skipped}


@router.post("/process")
def process_sequences(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Process due sequence steps — generate AI drafts → create PendingEmail records."""
    now = now_tw()
    due = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.status == "active",
        SequenceEnrollment.next_send_at <= now,
    ).all()

    created = 0
    for enrollment in due:
        seq = db.query(EmailSequence).filter(EmailSequence.id == enrollment.sequence_id).first()
        if not seq:
            continue
        steps = json.loads(seq.steps)
        if enrollment.current_step >= len(steps):
            enrollment.status = "completed"
            continue

        step = steps[enrollment.current_step]
        lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
        if not lead or not lead.email:
            enrollment.current_step += 1
            continue

        # Generate AI draft
        subject, body_text = _gen_draft(lead, step["template_type"])

        pending = PendingEmail(
            lead_id=lead.id,
            enrollment_id=enrollment.id,
            to_email=lead.email,
            subject=subject,
            body=body_text,
        )
        db.add(pending)

        # Advance step
        enrollment.current_step += 1
        if enrollment.current_step < len(steps):
            next_day = steps[enrollment.current_step]["day"]
            prev_day = step["day"]
            enrollment.next_send_at = now + timedelta(days=(next_day - prev_day))
        else:
            enrollment.status = "completed"
            enrollment.next_send_at = None

        created += 1

    db.commit()
    return {"processed": len(due), "emails_created": created}


def _gen_draft(lead, template_type: str):
    hint = TEMPLATES.get(template_type, TEMPLATES["intro"])
    if not GEMINI_API_KEY:
        return f"【{template_type}】{lead.company_name}", f"您好，\n\n這是關於{lead.company_name}的開發信。\n\n敬上"

    prompt = f"""你是數位行銷業務，撰寫開發信。
公司：{lead.company_name}，聯絡人：{lead.contact_name or "負責人"}，職稱：{lead.title or ""}
類型：{template_type}，指引：{hint}
請用繁體中文。格式嚴格如下：
SUBJECT: <主旨>
BODY:
<內文>"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        if "SUBJECT:" in text and "BODY:" in text:
            parts = text.split("BODY:", 1)
            subject = parts[0].replace("SUBJECT:", "").strip()
            body = parts[1].strip()
            return subject, body
        lines = text.split("\n")
        return lines[0], "\n".join(lines[1:]).strip()
    except Exception:
        return f"【{template_type}】{lead.company_name}", "（AI 生成失敗，請手動編輯）"


@router.get("/pending")
def list_pending(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(PendingEmail).filter(PendingEmail.status == "pending")
    if current_user.role == UserRole.sales:
        q = q.join(Lead).filter(Lead.assigned_to == current_user.id)
    emails = q.order_by(PendingEmail.created_at).all()
    result = []
    for e in emails:
        lead = db.query(Lead).filter(Lead.id == e.lead_id).first()
        result.append({
            "id": str(e.id),
            "lead_id": str(e.lead_id),
            "company_name": lead.company_name if lead else "",
            "to_email": e.to_email,
            "subject": e.subject,
            "body": e.body,
            "status": e.status,
            "created_at": e.created_at.isoformat(),
        })
    return result


@router.post("/pending/{email_id}/send")
def send_pending(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pe = db.query(PendingEmail).filter(PendingEmail.id == email_id).first()
    if not pe:
        raise HTTPException(status_code=404, detail="Not found")

    # Mark as sent + record activity
    pe.status = "sent"
    act = LeadActivity(
        lead_id=pe.lead_id,
        type=ActivityType.email_sent,
        content=f"序列信件已發送\n主旨：{pe.subject}",
        created_by=current_user.id,
    )
    db.add(act)
    db.commit()
    return {"message": "marked as sent"}


@router.post("/pending/{email_id}/skip")
def skip_pending(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pe = db.query(PendingEmail).filter(PendingEmail.id == email_id).first()
    if not pe:
        raise HTTPException(status_code=404, detail="Not found")
    pe.status = "skipped"
    db.commit()
    return {"message": "skipped"}

