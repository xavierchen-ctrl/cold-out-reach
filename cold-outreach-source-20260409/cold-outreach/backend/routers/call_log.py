"""通話記錄管理."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, Lead, CallLog, LeadActivity, ActivityType

router = APIRouter(tags=["calls"])


def _call_to_dict(c: CallLog) -> dict:
    return {
        "id": str(c.id),
        "lead_id": str(c.lead_id),
        "caller_id": str(c.caller_id) if c.caller_id else None,
        "caller_name": c.caller.name if c.caller else None,
        "duration_seconds": c.duration_seconds,
        "outcome": c.outcome,
        "note": c.note,
        "called_at": c.called_at.isoformat() if c.called_at else None,
    }


OUTCOME_LABELS = {
    "answered": "接通",
    "no_answer": "未接",
    "voicemail": "語音信箱",
    "callback_requested": "要求回電",
}


@router.get("/api/leads/{lead_id}/calls")
def list_calls(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    calls = (
        db.query(CallLog)
        .filter(CallLog.lead_id == lead_id)
        .order_by(CallLog.called_at.desc())
        .all()
    )
    return [_call_to_dict(c) for c in calls]


@router.post("/api/leads/{lead_id}/calls")
def create_call(
    lead_id: UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    call = CallLog(
        lead_id=lead_id,
        caller_id=current_user.id,
        duration_seconds=body.get("duration_seconds"),
        outcome=body.get("outcome"),
        note=body.get("note"),
        called_at=datetime.utcnow(),
    )
    db.add(call)

    # Update engagement score for calls
    delta = 30 if body.get("outcome") == "answered" else 5
    lead.engagement_score = (lead.engagement_score or 0) + delta

    # Log activity
    outcome_label = OUTCOME_LABELS.get(body.get("outcome", ""), body.get("outcome", ""))
    act = LeadActivity(
        lead_id=lead_id,
        type=ActivityType.call_note,
        content=f"通話記錄\n結果：{outcome_label}\n時長：{body.get('duration_seconds', 0)} 秒\n備注：{body.get('note', '')}",
        created_by=current_user.id,
    )
    db.add(act)
    db.commit()
    db.refresh(call)
    return _call_to_dict(call)


@router.get("/api/calls/stats")
def call_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    all_calls = db.query(CallLog).all()
    total = len(all_calls)
    answered = sum(1 for c in all_calls if c.outcome == "answered")
    durations = [c.duration_seconds for c in all_calls if c.duration_seconds]
    avg_duration = sum(durations) / len(durations) if durations else 0

    return {
        "total_calls": total,
        "answered": answered,
        "answer_rate": f"{round(answered / total * 100, 1)}%" if total > 0 else "0%",
        "avg_duration_seconds": round(avg_duration),
        "no_answer": sum(1 for c in all_calls if c.outcome == "no_answer"),
        "voicemail": sum(1 for c in all_calls if c.outcome == "voicemail"),
        "callback_requested": sum(1 for c in all_calls if c.outcome == "callback_requested"),
    }
