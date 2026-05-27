import re
from datetime import datetime
from utils import now_tw
from typing import List, Optional, Any
from uuid import UUID
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import KeywordTracker, Lead
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/keyword_trackers", tags=["keyword_trackers"])


class KeywordTrackerCreate(BaseModel):
    lead_id: Optional[str] = None
    keywords: List[str]
    website_url: str


class KeywordTrackerOut(BaseModel):
    id: str
    lead_id: Optional[str]
    keywords: Optional[List[str]]
    website_url: Optional[str]
    last_checked: Optional[str]
    last_result: Optional[Any]
    created_at: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            lead_id=str(obj.lead_id) if obj.lead_id else None,
            keywords=obj.keywords or [],
            website_url=obj.website_url,
            last_checked=obj.last_checked.isoformat() if obj.last_checked else None,
            last_result=obj.last_result,
            created_at=obj.created_at.isoformat(),
        )


@router.get("")
def list_trackers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trackers = db.query(KeywordTracker).order_by(KeywordTracker.created_at.desc()).all()
    return [KeywordTrackerOut.from_orm(t) for t in trackers]


@router.post("")
def create_tracker(body: KeywordTrackerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    data = body.model_dump()
    if data.get("lead_id"):
        try:
            lead_uuid = UUID(data["lead_id"])
            lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
            data["lead_id"] = lead_uuid
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid lead_id")
    else:
        data["lead_id"] = None
    
    tracker = KeywordTracker(**data)
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    return KeywordTrackerOut.from_orm(tracker)


@router.delete("/{tracker_id}")
def delete_tracker(tracker_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tracker = db.query(KeywordTracker).filter(KeywordTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    db.delete(tracker)
    db.commit()
    return {"message": "deleted"}


@router.post("/{tracker_id}/check")
async def check_keywords(tracker_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tracker = db.query(KeywordTracker).filter(KeywordTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    
    if not tracker.website_url:
        raise HTTPException(status_code=400, detail="No website URL configured")
    
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                tracker.website_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ColdOutreach/1.0)"},
            )
            html = resp.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch website: {str(e)}")
    
    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style tags for cleaner text
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    
    results = {}
    for keyword in (tracker.keywords or []):
        # Case-insensitive search
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        matches = list(pattern.finditer(text))
        if matches:
            # Get context around first match
            m = matches[0]
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            context = text[start:end].strip()
            results[keyword] = {"found": True, "count": len(matches), "context": context}
        else:
            results[keyword] = {"found": False, "count": 0, "context": None}
    
    tracker.last_checked = now_tw()
    tracker.last_result = results
    db.commit()
    db.refresh(tracker)
    
    return {
        "tracker": KeywordTrackerOut.from_orm(tracker),
        "results": results,
    }
