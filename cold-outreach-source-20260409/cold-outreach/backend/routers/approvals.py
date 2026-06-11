from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import User, Lead, PendingLeadApproval, UserRole
from auth import get_current_user
from utils import now_tw

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _is_approver(user: User) -> bool:
    return user.role in (UserRole.team_lead, UserRole.admin, UserRole.manager)


class ReviewRequest(BaseModel):
    decision: str          # "approved" | "rejected"
    note: Optional[str] = None


@router.get("/leads/pending-count")
def pending_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_approver(current_user):
        return {"count": 0}
    count = db.query(PendingLeadApproval).filter(PendingLeadApproval.status == "pending").count()
    return {"count": count}


@router.get("/leads")
def list_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_approver(current_user):
        raise HTTPException(status_code=403, detail="無審核權限")

    approvals = (
        db.query(PendingLeadApproval)
        .order_by(PendingLeadApproval.submitted_at.desc())
        .all()
    )
    result = []
    for a in approvals:
        submitter = db.query(User).filter(User.id == a.submitted_by).first()
        tl_reviewer = db.query(User).filter(User.id == a.team_lead_reviewer_id).first() if a.team_lead_reviewer_id else None
        ivy_reviewer = db.query(User).filter(User.id == a.ivy_reviewer_id).first() if a.ivy_reviewer_id else None
        result.append({
            "id": str(a.id),
            "submitted_by_name": submitter.name if submitter else "未知",
            "submitted_at": a.submitted_at.isoformat(),
            "conflict_company": a.conflict_company,
            "lead_data": a.lead_data,
            "status": a.status,
            "team_lead_decision": a.team_lead_decision,
            "team_lead_reviewer_name": tl_reviewer.name if tl_reviewer else None,
            "ivy_decision": a.ivy_decision,
            "ivy_reviewer_name": ivy_reviewer.name if ivy_reviewer else None,
            "review_note": a.review_note,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        })
    return result


@router.post("/leads/{approval_id}/review")
def review_approval(
    approval_id: UUID,
    body: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_approver(current_user):
        raise HTTPException(status_code=403, detail="無審核權限")

    approval = db.query(PendingLeadApproval).filter(PendingLeadApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="審核單不存在")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="此審核單已處理完畢")

    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision 必須是 approved 或 rejected")

    is_manager = current_user.role in (UserRole.admin, UserRole.manager)
    is_team_lead = current_user.role in (UserRole.team_lead, UserRole.admin)

    if is_manager:
        approval.ivy_decision = body.decision
        approval.ivy_reviewer_id = current_user.id
    if is_team_lead:
        approval.team_lead_decision = body.decision
        approval.team_lead_reviewer_id = current_user.id

    if body.note:
        approval.review_note = body.note

    # 任一方拒絕 → 直接退回
    if approval.team_lead_decision == "rejected" or approval.ivy_decision == "rejected":
        approval.status = "rejected"
        approval.resolved_at = now_tw()

    # 雙方均核准 → 建立名單
    elif approval.team_lead_decision == "approved" and approval.ivy_decision == "approved":
        lead_data = {k: v for k, v in approval.lead_data.items() if v is not None}
        lead = Lead(**lead_data)
        db.add(lead)
        approval.status = "approved"
        approval.resolved_at = now_tw()

    db.commit()
    return {"status": approval.status}
