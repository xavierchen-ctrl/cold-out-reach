import hmac
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Webhook, WebhookLog
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

SUPPORTED_EVENTS = [
    "lead.status_changed",
    "lead.won",
    "lead.lost",
    "email.replied",
    "meeting.scheduled",
]


class WebhookCreate(BaseModel):
    name: Optional[str] = None
    url: str
    events: List[str]
    secret: Optional[str] = None
    is_active: bool = True


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookOut(BaseModel):
    id: str
    name: Optional[str]
    url: str
    events: Optional[List[str]]
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            name=obj.name,
            url=obj.url,
            events=obj.events or [],
            is_active=obj.is_active,
            created_at=obj.created_at.isoformat(),
        )


class WebhookLogOut(BaseModel):
    id: str
    webhook_id: str
    event: Optional[str]
    payload: Optional[str]
    response_status: Optional[int]
    created_at: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            webhook_id=str(obj.webhook_id),
            event=obj.event,
            payload=obj.payload,
            response_status=obj.response_status,
            created_at=obj.created_at.isoformat(),
        )


@router.get("")
def list_webhooks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhooks = db.query(Webhook).order_by(Webhook.created_at.desc()).all()
    return [WebhookOut.from_orm(w) for w in webhooks]


@router.post("")
def create_webhook(body: WebhookCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = Webhook(**body.model_dump())
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return WebhookOut.from_orm(webhook)


@router.put("/{webhook_id}")
def update_webhook(webhook_id: UUID, body: WebhookUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(webhook, field, value)
    db.commit()
    db.refresh(webhook)
    return WebhookOut.from_orm(webhook)


@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(webhook)
    db.commit()
    return {"message": "deleted"}


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    payload = {
        "event": "webhook.test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"message": "This is a test webhook from Cold Outreach Platform"},
    }
    
    status_code = await _fire_webhook_payload(webhook, "webhook.test", payload, db)
    return {"message": f"Test sent, response status: {status_code}"}


@router.get("/{webhook_id}/logs")
def get_webhook_logs(webhook_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    logs = db.query(WebhookLog).filter(WebhookLog.webhook_id == webhook_id).order_by(WebhookLog.created_at.desc()).limit(10).all()
    return [WebhookLogOut.from_orm(l) for l in logs]


async def _fire_webhook_payload(webhook: Webhook, event: str, payload: dict, db: Session) -> int:
    payload_str = json.dumps(payload)
    headers = {"Content-Type": "application/json", "X-Event": event}
    
    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        headers["X-Signature"] = f"sha256={sig}"
    
    status_code = 0
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook.url, content=payload_str, headers=headers)
            status_code = resp.status_code
    except Exception:
        status_code = 0
    
    log = WebhookLog(
        webhook_id=webhook.id,
        event=event,
        payload=payload_str,
        response_status=status_code,
    )
    db.add(log)
    db.commit()
    return status_code


async def trigger_webhooks(event: str, data: dict, db: Session):
    """Call this from other routers to trigger relevant webhooks."""
    webhooks = db.query(Webhook).filter(Webhook.is_active == True).all()
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    for webhook in webhooks:
        if webhook.events and event in webhook.events:
            await _fire_webhook_payload(webhook, event, payload, db)
