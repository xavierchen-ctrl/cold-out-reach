from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Lead, LeadStatus, LeadActivity, ActivityType, UserRole, User
from auth import get_current_user

router = APIRouter(prefix="/api/leads/bulk", tags=["bulk"])


class BulkStatusBody(BaseModel):
    lead_ids: List[UUID]
    status: LeadStatus


class BulkAssignBody(BaseModel):
    lead_ids: List[UUID]
    user_id: UUID


class BulkDeleteBody(BaseModel):
    lead_ids: List[UUID]


@router.post("/status")
def bulk_status(
    body: BulkStatusBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    leads = db.query(Lead).filter(Lead.id.in_(body.lead_ids)).all()
    updated = 0
    for lead in leads:
        if current_user.role == UserRole.sales and str(lead.assigned_to) != str(current_user.id):
            continue
        old = lead.status
        lead.status = body.status
        act = LeadActivity(
            lead_id=lead.id,
            type=ActivityType.status_change,
            content=f"{old.value} → {body.status.value}（批量操作）",
            created_by=current_user.id,
        )
        db.add(act)
        updated += 1
    db.commit()
    return {"updated": updated}


@router.post("/assign")
def bulk_assign(
    body: BulkAssignBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    target = db.query(User).filter(User.id == body.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    leads = db.query(Lead).filter(Lead.id.in_(body.lead_ids)).all()
    for lead in leads:
        lead.assigned_to = body.user_id
    db.commit()
    return {"updated": len(leads)}


@router.post("/delete")
def bulk_delete(
    body: BulkDeleteBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.sales:
        raise HTTPException(status_code=403, detail="Sales cannot bulk delete leads")
    leads = db.query(Lead).filter(Lead.id.in_(body.lead_ids)).all()
    deleted = 0
    for lead in leads:
        db.delete(lead)
        deleted += 1
    db.commit()
    return {"deleted": deleted}
