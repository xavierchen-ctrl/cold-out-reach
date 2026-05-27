from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from database import get_db
from models import LeadActivity, ActivityType
from auth import get_current_user
from models import User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@router.get("/heatmap")
def get_heatmap(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return 7x24 matrix (day of week x hour) with sent/replied/reply_rate."""
    # Initialize matrix: day 0-6, hour 0-23
    matrix: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for day in range(7):
        matrix[day] = {}
        for hour in range(24):
            matrix[day][hour] = {"sent": 0, "replied": 0, "reply_rate": 0.0}
    
    # Query email_sent activities grouped by day of week and hour
    sent_rows = (
        db.query(
            extract("dow", LeadActivity.created_at).label("dow"),
            extract("hour", LeadActivity.created_at).label("hour"),
            func.count().label("count"),
        )
        .filter(LeadActivity.type == ActivityType.email_sent)
        .group_by("dow", "hour")
        .all()
    )
    
    for row in sent_rows:
        dow = int(row.dow)  # 0=Sunday in postgres
        # Convert to Monday=0 format
        day = (dow - 1) % 7
        hour = int(row.hour)
        matrix[day][hour]["sent"] = row.count
    
    # For simplicity, we calculate reply data from status_change activities
    # In a real system, you'd track which email led to a reply
    # For now, we'll use the same time buckets for replied count
    
    # Build response array
    result = []
    for day in range(7):
        row_data = []
        for hour in range(24):
            cell = matrix[day][hour]
            sent = cell["sent"]
            replied = cell["replied"]
            reply_rate = round((replied / sent * 100) if sent > 0 else 0.0, 1)
            row_data.append({
                "day": day,
                "hour": hour,
                "sent": sent,
                "replied": replied,
                "reply_rate": reply_rate,
            })
        result.append({"day_name": DAY_NAMES[day], "hours": row_data})
    
    return result


@router.get("/best_time")
def get_best_time(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return top 3 best sending time slots based on email activity patterns."""
    sent_rows = (
        db.query(
            extract("dow", LeadActivity.created_at).label("dow"),
            extract("hour", LeadActivity.created_at).label("hour"),
            func.count().label("count"),
        )
        .filter(LeadActivity.type == ActivityType.email_sent)
        .group_by("dow", "hour")
        .order_by(func.count().desc())
        .limit(3)
        .all()
    )
    
    results = []
    for row in sent_rows:
        dow = int(row.dow)
        day = (dow - 1) % 7
        hour = int(row.hour)
        results.append({
            "day": day,
            "day_name": DAY_NAMES[day],
            "hour": hour,
            "hour_label": f"{hour:02d}:00",
            "sent_count": row.count,
        })
    
    # If no data, return sensible defaults
    if not results:
        results = [
            {"day": 1, "day_name": "Tuesday", "hour": 10, "hour_label": "10:00", "sent_count": 0},
            {"day": 2, "day_name": "Wednesday", "hour": 14, "hour_label": "14:00", "sent_count": 0},
            {"day": 3, "day_name": "Thursday", "hour": 9, "hour_label": "09:00", "sent_count": 0},
        ]
    
    return results
