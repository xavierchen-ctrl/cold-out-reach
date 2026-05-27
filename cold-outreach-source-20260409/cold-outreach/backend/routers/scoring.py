import re
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Lead, LeadStatus, UserRole, EmailOpen, EmailClick, CallLog, CadenceStepLog, CadenceEnrollment
from auth import get_current_user
from schemas import ScoreResponse

router = APIRouter(prefix="/api/leads", tags=["scoring"])

GENERIC_EMAILS = {"info@", "service@", "contact@", "support@", "admin@", "no-reply@", "noreply@", "hello@"}


def _calc_score(lead: Lead):
    score = 50
    reasons = []

    # +20 company size >= 50
    if lead.company_size:
        nums = re.findall(r'\d+', lead.company_size)
        if nums and int(nums[-1]) >= 50:
            score += 20
            reasons.append("+20 公司規模≥50人")

    # +10 has email
    if lead.email:
        score += 10
        reasons.append("+10 有Email")
        # -5 generic email
        if any(g in lead.email.lower() for g in GENERIC_EMAILS):
            score -= 5
            reasons.append("-5 通用信箱")

    # +10 has phone
    if lead.phone:
        score += 10
        reasons.append("+10 有電話")

    # +10 exhibition source
    if lead.source and lead.source.startswith("exhibition:"):
        score += 10
        reasons.append("+10 會展來源")

    # +5 contact name
    if lead.contact_name:
        score += 5
        reasons.append("+5 有聯絡人")

    # +5 title
    if lead.title:
        score += 5
        reasons.append("+5 有職稱")

    # -10 lost
    if lead.status == LeadStatus.lost:
        score -= 10
        reasons.append("-10 已流失")

    score = max(0, min(100, score))
    return score, "、".join(reasons) if reasons else "基礎分"


def _calc_intent_score(lead: Lead, db: Session):
    """Calculate intent score based on engagement signals."""
    intent = 0
    breakdown = []

    # Email opens × 5
    opens = db.query(EmailOpen).filter(EmailOpen.lead_id == lead.id).count()
    if opens > 0:
        intent += opens * 5
        breakdown.append(f"開信 {opens} 次(+{opens*5})")

    # Email clicks × 10
    clicks = db.query(EmailClick).filter(EmailClick.lead_id == lead.id).count()
    if clicks > 0:
        intent += clicks * 10
        breakdown.append(f"點擊連結 {clicks} 次(+{clicks*10})")

    # Call logs × 8
    call_count = db.query(CallLog).filter(CallLog.lead_id == lead.id).count()
    if call_count > 0:
        intent += call_count * 8
        breakdown.append(f"通話記錄 {call_count} 筆(+{call_count*8})")

    # Cadence interactions × 3 (completed steps)
    cadence_interactions = db.query(CadenceStepLog).join(
        CadenceEnrollment, CadenceStepLog.enrollment_id == CadenceEnrollment.id
    ).filter(
        CadenceEnrollment.lead_id == lead.id,
        CadenceStepLog.status == "done",
    ).count()
    if cadence_interactions > 0:
        intent += cadence_interactions * 3
        breakdown.append(f"Cadence 互動 {cadence_interactions} 次(+{cadence_interactions*3})")

    return intent, breakdown


@router.post("/{lead_id}/score", response_model=ScoreResponse)
def score_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if current_user.role == UserRole.sales and str(lead.assigned_to) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    score, reason = _calc_score(lead)

    # Intent score enhancement
    intent, intent_breakdown = _calc_intent_score(lead, db)
    if intent_breakdown:
        full_reason = reason + "｜意圖:" + "、".join(intent_breakdown)
    else:
        full_reason = reason
    # Auto-promote to MQL if intent >= 30 and current status is new/contacted
    if intent >= 30 and lead.status in (LeadStatus.new, LeadStatus.contacted):
        lead.status = LeadStatus.mql

    lead.score = score
    lead.score_reason = full_reason
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return ScoreResponse(lead_id=lead.id, score=score, score_reason=full_reason, updated_at=lead.updated_at)


class BatchScoreRequest:
    pass


from pydantic import BaseModel


class BatchScoreBody(BaseModel):
    lead_ids: Optional[List[UUID]] = None
    all: bool = False


@router.post("/score/batch")
def score_batch(
    body: BatchScoreBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(Lead)
    if current_user.role == UserRole.sales:
        q = q.filter(Lead.assigned_to == current_user.id)
    if not body.all and body.lead_ids:
        q = q.filter(Lead.id.in_(body.lead_ids))

    leads = q.all()
    updated = 0
    for lead in leads:
        score, reason = _calc_score(lead)
        intent, intent_breakdown = _calc_intent_score(lead, db)
        if intent_breakdown:
            full_reason = reason + "｜意圖:" + "、".join(intent_breakdown)
        else:
            full_reason = reason
        if intent >= 30 and lead.status in (LeadStatus.new, LeadStatus.contacted):
            lead.status = LeadStatus.mql
        lead.score = score
        lead.score_reason = full_reason
        lead.updated_at = datetime.utcnow()
        updated += 1

    db.commit()
    return {"updated": updated}
