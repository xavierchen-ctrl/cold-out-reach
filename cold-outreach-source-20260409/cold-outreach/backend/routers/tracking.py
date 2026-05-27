"""Email open & click tracking."""
import os
import base64
from datetime import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from database import get_db
from models import EmailOpen, EmailClick, Lead

router = APIRouter(prefix="/api/track", tags=["tracking"])

# Base URL for tracking pixel (override via env)
TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://localhost:8000")

# 1x1 transparent GIF
TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

ENGAGEMENT_SCORE_OPEN = 10
ENGAGEMENT_SCORE_CLICK = 20


def _get_client_ip(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    return ip


def _update_engagement(db: Session, lead_id: str, delta: int):
    """Add delta to lead's engagement_score."""
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            current = lead.engagement_score or 0
            lead.engagement_score = current + delta
            db.commit()
    except Exception:
        pass


@router.get("/open/{email_id}")
def track_open(
    email_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record email open and return 1x1 transparent pixel."""
    # Extract lead_id from email_id format "lead_id_timestamp"
    parts = email_id.split("_")
    lead_id_str = parts[0] if parts else email_id

    ip = _get_client_ip(request)

    try:
        open_event = EmailOpen(
            email_id=email_id,
            lead_id=lead_id_str,
            opened_at=datetime.utcnow(),
            ip=ip,
        )
        db.add(open_event)
        db.commit()
        # Update engagement score
        _update_engagement(db, lead_id_str, ENGAGEMENT_SCORE_OPEN)
    except Exception:
        pass

    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/click/{email_id}")
def track_click(
    email_id: str,
    url: str = "",
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Record link click and redirect to original URL."""
    parts = email_id.split("_")
    lead_id_str = parts[0] if parts else email_id

    ip = _get_client_ip(request) if request else "unknown"
    original_url = unquote(url) if url else "/"

    try:
        click_event = EmailClick(
            email_id=email_id,
            lead_id=lead_id_str if lead_id_str else None,
            url=original_url,
            clicked_at=datetime.utcnow(),
            ip=ip,
        )
        db.add(click_event)
        db.commit()
        # Update engagement score
        if lead_id_str:
            _update_engagement(db, lead_id_str, ENGAGEMENT_SCORE_CLICK)
    except Exception:
        pass

    return RedirectResponse(url=original_url, status_code=302)


def inject_tracking_links(body: str, email_id: str, base_url: str) -> str:
    """Replace https:// links in body with click tracking redirects."""
    import re
    from urllib.parse import quote

    def replace_link(match):
        original = match.group(0)
        # Don't double-wrap tracking links
        if "/api/track/" in original:
            return original
        encoded = quote(original, safe="")
        return f"{base_url}/api/track/click/{email_id}?url={encoded}"

    # Replace bare URLs (not already in href="...")
    return re.sub(r'https://[^\s<>"\']+', replace_link, body)
