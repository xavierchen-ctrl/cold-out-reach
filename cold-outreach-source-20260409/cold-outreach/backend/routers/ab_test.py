import random
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import ABTest, Lead
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/ab_tests", tags=["ab_tests"])


class ABTestCreate(BaseModel):
    name: str
    subject_a: str
    body_a: str
    subject_b: str
    body_b: str


class ABTestOut(BaseModel):
    id: str
    name: str
    subject_a: str
    body_a: str
    subject_b: str
    body_b: str
    status: str
    sent_a: int
    sent_b: int
    opened_a: int
    opened_b: int
    replied_a: int
    replied_b: int
    created_at: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            name=obj.name,
            subject_a=obj.subject_a,
            body_a=obj.body_a,
            subject_b=obj.subject_b,
            body_b=obj.body_b,
            status=obj.status,
            sent_a=obj.sent_a,
            sent_b=obj.sent_b,
            opened_a=obj.opened_a,
            opened_b=obj.opened_b,
            replied_a=obj.replied_a,
            replied_b=obj.replied_b,
            created_at=obj.created_at.isoformat(),
        )


@router.get("")
def list_ab_tests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tests = db.query(ABTest).order_by(ABTest.created_at.desc()).all()
    return [ABTestOut.from_orm(t) for t in tests]


@router.post("")
def create_ab_test(body: ABTestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    test = ABTest(**body.model_dump(), created_by=current_user.id)
    db.add(test)
    db.commit()
    db.refresh(test)
    return ABTestOut.from_orm(test)


class SendABTestBody(BaseModel):
    lead_ids: List[str]


@router.post("/{test_id}/send")
def send_ab_test(test_id: UUID, body: SendABTestBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="AB Test not found")
    
    # Randomly split into two groups
    shuffled = list(body.lead_ids)
    random.shuffle(shuffled)
    mid = len(shuffled) // 2
    group_a = shuffled[:mid]
    group_b = shuffled[mid:]
    
    # In a real implementation, this would trigger email sends via Gmail
    # For now, record the intent and update counters
    test.sent_a = test.sent_a + len(group_a)
    test.sent_b = test.sent_b + len(group_b)
    db.commit()
    
    return {
        "message": f"Scheduled: Group A={len(group_a)} leads, Group B={len(group_b)} leads",
        "group_a_ids": group_a,
        "group_b_ids": group_b,
    }


@router.get("/{test_id}/results")
def get_ab_results(test_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="AB Test not found")
    
    open_rate_a = (test.opened_a / test.sent_a * 100) if test.sent_a > 0 else 0
    open_rate_b = (test.opened_b / test.sent_b * 100) if test.sent_b > 0 else 0
    reply_rate_a = (test.replied_a / test.sent_a * 100) if test.sent_a > 0 else 0
    reply_rate_b = (test.replied_b / test.sent_b * 100) if test.sent_b > 0 else 0
    
    # Determine winner based on reply rate, fallback to open rate
    winner = None
    if reply_rate_a > reply_rate_b:
        winner = "A"
    elif reply_rate_b > reply_rate_a:
        winner = "B"
    elif open_rate_a > open_rate_b:
        winner = "A"
    elif open_rate_b > open_rate_a:
        winner = "B"
    
    return {
        "test": ABTestOut.from_orm(test),
        "a": {"sent": test.sent_a, "opened": test.opened_a, "replied": test.replied_a, "open_rate": round(open_rate_a, 1), "reply_rate": round(reply_rate_a, 1)},
        "b": {"sent": test.sent_b, "opened": test.opened_b, "replied": test.replied_b, "open_rate": round(open_rate_b, 1), "reply_rate": round(reply_rate_b, 1)},
        "winner": winner,
    }


@router.patch("/{test_id}")
def update_ab_test(test_id: UUID, body: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="AB Test not found")
    for k, v in body.items():
        if hasattr(test, k):
            setattr(test, k, v)
    db.commit()
    db.refresh(test)
    return ABTestOut.from_orm(test)
