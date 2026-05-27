"""ICP (Ideal Customer Profile) CRUD."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import ICPProfile

router = APIRouter(prefix="/api/icp", tags=["icp"])


class ICPCreate(BaseModel):
    name: str
    industries: Optional[List[str]] = []
    company_sizes: Optional[List[str]] = []
    titles: Optional[List[str]] = []
    locations: Optional[List[str]] = []


class ICPOut(BaseModel):
    id: UUID
    name: str
    industries: List[str]
    company_sizes: List[str]
    titles: List[str]
    locations: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ICPOut])
def list_icps(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return db.query(ICPProfile).order_by(ICPProfile.created_at.desc()).all()


@router.post("", response_model=ICPOut)
def create_icp(
    body: ICPCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    icp = ICPProfile(
        name=body.name,
        industries=body.industries or [],
        company_sizes=body.company_sizes or [],
        titles=body.titles or [],
        locations=body.locations or [],
    )
    db.add(icp)
    db.commit()
    db.refresh(icp)
    return icp


@router.get("/{icp_id}", response_model=ICPOut)
def get_icp(
    icp_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    icp = db.query(ICPProfile).filter(ICPProfile.id == icp_id).first()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP not found")
    return icp


@router.patch("/{icp_id}", response_model=ICPOut)
def update_icp(
    icp_id: UUID,
    body: ICPCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    icp = db.query(ICPProfile).filter(ICPProfile.id == icp_id).first()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP not found")
    icp.name = body.name
    icp.industries = body.industries or []
    icp.company_sizes = body.company_sizes or []
    icp.titles = body.titles or []
    icp.locations = body.locations or []
    db.commit()
    db.refresh(icp)
    return icp


@router.delete("/{icp_id}")
def delete_icp(
    icp_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    icp = db.query(ICPProfile).filter(ICPProfile.id == icp_id).first()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP not found")
    db.delete(icp)
    db.commit()
    return {"message": "deleted"}
