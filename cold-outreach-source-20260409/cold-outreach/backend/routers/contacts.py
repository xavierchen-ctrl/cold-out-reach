from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Contact, Lead
from auth import get_current_user
from models import User

router = APIRouter(tags=["contacts"])


class ContactCreate(BaseModel):
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    notes: Optional[str] = None
    is_primary: bool = False


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    notes: Optional[str] = None
    is_primary: Optional[bool] = None


class ContactOut(BaseModel):
    id: str
    company_id: str
    name: str
    title: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    linkedin: Optional[str]
    notes: Optional[str]
    is_primary: bool
    created_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            company_id=str(obj.company_id),
            name=obj.name,
            title=obj.title,
            email=obj.email,
            phone=obj.phone,
            linkedin=obj.linkedin,
            notes=obj.notes,
            is_primary=obj.is_primary,
            created_at=obj.created_at.isoformat(),
        )


@router.get("/api/leads/{lead_id}/contacts")
def list_contacts(lead_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    contacts = db.query(Contact).filter(Contact.company_id == lead_id).order_by(Contact.is_primary.desc(), Contact.created_at).all()
    return [ContactOut.from_orm(c) for c in contacts]


@router.post("/api/leads/{lead_id}/contacts")
def create_contact(lead_id: UUID, body: ContactCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    contact = Contact(company_id=lead_id, **body.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactOut.from_orm(contact)


@router.put("/api/contacts/{contact_id}")
def update_contact(contact_id: UUID, body: ContactUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return ContactOut.from_orm(contact)


@router.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"message": "deleted"}


@router.post("/api/contacts/{contact_id}/set_primary")
def set_primary_contact(contact_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    # unset all primaries for this lead
    db.query(Contact).filter(Contact.company_id == contact.company_id).update({"is_primary": False})
    contact.is_primary = True
    db.commit()
    db.refresh(contact)
    return ContactOut.from_orm(contact)
