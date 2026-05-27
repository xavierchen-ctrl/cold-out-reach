from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Tag, LeadTag, Lead
from auth import get_current_user
from models import User

router = APIRouter(tags=["tags"])


class TagCreate(BaseModel):
    name: str
    color: str = "#6366f1"


class TagOut(BaseModel):
    id: str
    name: str
    color: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(id=str(obj.id), name=obj.name, color=obj.color)


@router.get("/api/tags")
def list_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return [TagOut.from_orm(t) for t in tags]


@router.post("/api/tags")
def create_tag(body: TagCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(Tag).filter(Tag.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tag name already exists")
    tag = Tag(**body.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return TagOut.from_orm(tag)


@router.delete("/api/tags/{tag_id}")
def delete_tag(tag_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return {"message": "deleted"}


class AddTagsBody(BaseModel):
    tag_ids: List[str]


@router.post("/api/leads/{lead_id}/tags")
def add_lead_tags(lead_id: UUID, body: AddTagsBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for tag_id_str in body.tag_ids:
        try:
            tag_id = UUID(tag_id_str)
        except Exception:
            continue
        # check tag exists
        tag = db.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            continue
        # check if already assigned
        existing = db.query(LeadTag).filter(LeadTag.lead_id == lead_id, LeadTag.tag_id == tag_id).first()
        if not existing:
            lt = LeadTag(lead_id=lead_id, tag_id=tag_id)
            db.add(lt)
    db.commit()
    return {"message": "tags added"}


@router.delete("/api/leads/{lead_id}/tags/{tag_id}")
def remove_lead_tag(lead_id: UUID, tag_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lt = db.query(LeadTag).filter(LeadTag.lead_id == lead_id, LeadTag.tag_id == tag_id).first()
    if not lt:
        raise HTTPException(status_code=404, detail="Tag assignment not found")
    db.delete(lt)
    db.commit()
    return {"message": "removed"}


@router.get("/api/leads/{lead_id}/tags")
def get_lead_tags(lead_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead_tags = db.query(LeadTag).filter(LeadTag.lead_id == lead_id).all()
    result = []
    for lt in lead_tags:
        tag = db.query(Tag).filter(Tag.id == lt.tag_id).first()
        if tag:
            result.append(TagOut.from_orm(tag))
    return result
