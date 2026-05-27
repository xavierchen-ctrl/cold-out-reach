import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"


def get_line_token() -> Optional[str]:
    return os.environ.get("LINE_NOTIFY_TOKEN")


async def send_line_notify(message: str) -> bool:
    token = get_line_token()
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                LINE_NOTIFY_URL,
                headers={"Authorization": f"Bearer {token}"},
                data={"message": message},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def notify_lead_won(company_name: str, contact_name: str, assigned_user_name: str):
    message = f"\n🎉 新成交！{company_name} - {contact_name} ({assigned_user_name})"
    await send_line_notify(message)


async def notify_meeting_scheduled(company_name: str, contact_name: str, assigned_user_name: str):
    message = f"\n📅 會議確認！{company_name} - {contact_name} ({assigned_user_name})"
    await send_line_notify(message)


class TestNotifyBody(BaseModel):
    message: Optional[str] = "🧪 Cold Outreach 測試通知"


@router.post("/test")
async def test_notification(body: TestNotifyBody, current_user: User = Depends(get_current_user)):
    token = get_line_token()
    if not token:
        raise HTTPException(status_code=400, detail="LINE_NOTIFY_TOKEN not configured")
    success = await send_line_notify(body.message or "🧪 Cold Outreach 測試通知")
    if success:
        return {"message": "通知已發送"}
    raise HTTPException(status_code=500, detail="Failed to send LINE notification")


@router.get("/settings")
def get_notification_settings(current_user: User = Depends(get_current_user)):
    token = get_line_token()
    return {
        "line_notify_configured": bool(token),
        "line_notify_token_preview": f"...{token[-6:]}" if token else None,
        "triggers": ["won", "meeting_scheduled"],
    }
