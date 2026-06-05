import os
import json
import base64
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from database import get_db
from models import User, Lead, LeadActivity, ActivityType, LeadStatus
from schemas import SendEmailRequest, BulkSendRequest
from auth import get_current_user

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/gmail/callback")


def _get_flow(state: str = None) -> Flow:
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=GOOGLE_REDIRECT_URI, state=state
    )
    return flow


@router.get("/auth")
def gmail_auth(current_user: User = Depends(get_current_user)):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    flow = _get_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", state=str(current_user.id)
    )
    return {"auth_url": auth_url}


@router.get("/callback")
def gmail_callback(code: str, state: str, db: Session = Depends(get_db)):
    flow = _get_flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
    }

    # 取得使用者的 Gmail 信箱
    try:
        import requests as _req
        r = _req.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=5,
        )
        if r.status_code == 200:
            token_data["email"] = r.json().get("email", "")
    except Exception:
        pass

    user = db.query(User).filter(User.id == state).first()
    if user:
        user.gmail_token = json.dumps(token_data)
        db.commit()

    gmail_email = token_data.get("email", "")
    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Gmail 綁定成功</title></head>
<body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f9fafb;">
  <div style="text-align:center;padding:2rem;background:white;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.1)">
    <div style="font-size:2.5rem;margin-bottom:.5rem">✅</div>
    <h2 style="margin:0 0 .5rem;color:#111">Gmail 綁定成功</h2>
    <p style="color:#6b7280;margin:0 0 1.5rem">{gmail_email}</p>
    <p style="color:#9ca3af;font-size:.875rem">此視窗將自動關閉…</p>
  </div>
  <script>
    if (window.opener) {{
      window.opener.postMessage({{type:'gmail-connected',email:{json.dumps(gmail_email)}}}, '*');
      setTimeout(() => window.close(), 1500);
    }}
  </script>
</body></html>""")


@router.get("/status")
def gmail_status(current_user: User = Depends(get_current_user)):
    """回傳目前使用者的 Gmail 綁定狀態"""
    if not current_user.gmail_token:
        return {"connected": False, "email": None}
    try:
        token_data = json.loads(current_user.gmail_token)
        return {"connected": True, "email": token_data.get("email")}
    except Exception:
        return {"connected": False, "email": None}


@router.delete("/disconnect")
def gmail_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解除 Gmail 綁定"""
    current_user.gmail_token = None
    db.commit()
    return {"ok": True}


@router.post("/send")
def send_email(
    body: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.gmail_token:
        raise HTTPException(status_code=400, detail="Gmail not connected. Please authorize first.")

    token_data = json.loads(current_user.gmail_token)
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    try:
        service = build("gmail", "v1", credentials=creds)

        if body.attachments:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body.body, "plain", "utf-8"))
            for att in body.attachments:
                mime_main, mime_sub = (att.mime_type + "/octet-stream").split("/", 1)[:2] if "/" in att.mime_type else ("application", "octet-stream")
                part = MIMEBase(mime_main, mime_sub)
                part.set_payload(base64.b64decode(att.content))
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=att.filename)
                msg.attach(part)
        else:
            msg = MIMEText(body.body, "plain", "utf-8")

        msg["To"] = body.to
        msg["Subject"] = body.subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail send failed: {str(e)}")

    # Log activity
    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if lead:
        activity = LeadActivity(
            lead_id=lead.id,
            type=ActivityType.email_sent,
            content=f"To: {body.to}\nSubject: {body.subject}\n\n{body.body}",
            created_by=current_user.id,
        )
        db.add(activity)
        db.commit()

    return {"message": "sent"}


def _replace_vars(text: str, lead: Lead) -> str:
    return (text
        .replace("{{company_name}}", lead.company_name or "")
        .replace("{{contact_name}}", lead.contact_name or "您好")
        .replace("{{industry}}", lead.industry or "")
        .replace("{{city}}", lead.city or "")
        .replace("{{title}}", lead.title or "")
        .replace("{{email}}", lead.email or "")
    )


@router.post("/bulk-send")
def bulk_send_email(
    body: BulkSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """合併列印群發：對每位名單個別套入變數後發送"""
    if not current_user.gmail_token:
        raise HTTPException(status_code=400, detail="Gmail not connected. Please authorize first.")
    if len(body.lead_ids) > 200:
        raise HTTPException(status_code=400, detail="單次群發上限 200 封")

    token_data = json.loads(current_user.gmail_token)
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )
    service = build("gmail", "v1", credentials=creds)

    import time
    sent, failed, errors = 0, 0, []

    for lead_id in body.lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead or not lead.email:
            failed += 1
            errors.append({"lead_id": str(lead_id), "error": "無 Email"})
            continue
        try:
            subject = _replace_vars(body.subject, lead)
            content = _replace_vars(body.body, lead)
            msg = MIMEText(content, "plain", "utf-8")
            msg["To"] = lead.email
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            activity = LeadActivity(
                lead_id=lead.id,
                type=ActivityType.email_sent,
                content=f"To: {lead.email}\nSubject: {subject}\n\n{content}",
                created_by=current_user.id,
            )
            db.add(activity)
            db.commit()
            sent += 1
            time.sleep(0.3)
        except Exception as e:
            failed += 1
            errors.append({"lead_id": str(lead_id), "error": str(e)})

    return {"sent": sent, "failed": failed, "errors": errors}


@router.post("/check_replies")
def check_replies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan Gmail inbox for replies to sent emails. Update lead status if reply found."""
    if not current_user.gmail_token:
        raise HTTPException(status_code=400, detail="Gmail not connected.")

    token_data = json.loads(current_user.gmail_token)
    # Need read scope; if only send scope, return gracefully
    scopes = token_data.get("scopes", [])
    read_scopes = ["https://www.googleapis.com/auth/gmail.readonly", "https://mail.google.com/"]
    has_read = any(s in read_scopes for s in scopes)
    if not has_read:
        return {"message": "Gmail read scope not granted. Re-authorize with full access.", "found": 0}

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=scopes,
    )

    try:
        service = build("gmail", "v1", credentials=creds)
        # Get sent emails with activity records
        sent_activities = (
            db.query(LeadActivity)
            .filter(LeadActivity.type == ActivityType.email_sent)
            .order_by(LeadActivity.created_at.desc())
            .limit(200)
            .all()
        )

        # Extract email addresses from sent activities
        found = 0
        for act in sent_activities:
            if not act.content:
                continue
            # Parse "To: email\nSubject: ..." from activity content
            to_match = re.search(r"To: (.+)", act.content)
            subject_match = re.search(r"Subject: (.+)", act.content)
            if not to_match or not subject_match:
                continue

            to_email = to_match.group(1).strip()
            subject = subject_match.group(1).strip()

            # Search inbox for replies from this email address
            query = f"from:{to_email} in:inbox"
            try:
                result = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
                messages = result.get("messages", [])
                if messages:
                    # Check if subject matches (reply subject contains original)
                    for msg_meta in messages[:3]:
                        msg = service.users().messages().get(
                            userId="me", id=msg_meta["id"], format="metadata",
                            metadataHeaders=["Subject", "From"]
                        ).execute()
                        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                        msg_subject = headers.get("Subject", "")
                        # Check if it's a reply to our subject
                        original_words = [w.lower() for w in subject.split() if len(w) > 3]
                        subject_words = [w.lower() for w in msg_subject.split() if len(w) > 3]
                        overlap = sum(1 for w in original_words if w in subject_words)
                        is_reply = overlap >= min(2, len(original_words)) or msg_subject.lower().startswith("re:")

                        if is_reply:
                            # Update lead status to replied
                            lead = db.query(Lead).filter(Lead.id == act.lead_id).first()
                            if lead and lead.status in (LeadStatus.new, LeadStatus.contacted):
                                old_status = lead.status
                                lead.status = LeadStatus.replied
                                lead.engagement_score = (lead.engagement_score or 0) + 50
                                reply_act = LeadActivity(
                                    lead_id=lead.id,
                                    type=ActivityType.status_change,
                                    content=f"[自動偵測回覆] {old_status.value} → replied\n來自：{to_email}\n主旨：{msg_subject}",
                                    created_by=current_user.id,
                                )
                                db.add(reply_act)
                                found += 1
                                break
            except Exception:
                continue

        db.commit()
        return {"message": f"掃描完成，發現 {found} 筆回覆", "found": found}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail check failed: {str(e)}")
