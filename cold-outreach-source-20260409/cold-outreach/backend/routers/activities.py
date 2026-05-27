from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, Lead, LeadActivity, UserRole
from schemas import ActivityCreate, ActivityOut
from auth import get_current_user

router = APIRouter(prefix="/api/leads", tags=["activities"])


def _check_lead_access(lead_id: UUID, user: User, db: Session) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if user.role == UserRole.sales and str(lead.assigned_to) != str(user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return lead


@router.get("/{lead_id}/activities", response_model=List[ActivityOut])
def list_activities(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_lead_access(lead_id, current_user, db)
    return (
        db.query(LeadActivity)
        .filter(LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.created_at.desc())
        .all()
    )


@router.post("/{lead_id}/activities", response_model=ActivityOut)
def create_activity(
    lead_id: UUID,
    body: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_lead_access(lead_id, current_user, db)
    activity = LeadActivity(
        lead_id=lead_id,
        type=body.type,
        content=body.content,
        created_by=current_user.id,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity
