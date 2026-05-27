import base64
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Attachment, Lead
from auth import get_current_user
from models import User

router = APIRouter(tags=["attachments"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes


class AttachmentUpload(BaseModel):
    # Mode A: file upload
    filename: Optional[str] = None
    file_data: Optional[str] = None   # base64 encoded
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    # Mode B: Google Drive link
    drive_url: Optional[str] = None
    drive_name: Optional[str] = None


class AttachmentOut(BaseModel):
    id: str
    lead_id: str
    filename: str
    file_size: Optional[int]
    file_type: Optional[str]
    drive_url: Optional[str]
    drive_name: Optional[str]
    is_drive_link: bool
    uploaded_by: Optional[str]
    created_at: str

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            lead_id=str(obj.lead_id),
            filename=obj.filename,
            file_size=obj.file_size,
            file_type=obj.file_type,
            drive_url=obj.drive_url,
            drive_name=obj.drive_name,
            is_drive_link=bool(obj.drive_url),
            uploaded_by=str(obj.uploaded_by) if obj.uploaded_by else None,
            created_at=obj.created_at.isoformat(),
        )


@router.get("/api/leads/{lead_id}/attachments")
def list_attachments(lead_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    attachments = db.query(Attachment).filter(Attachment.lead_id == lead_id).order_by(Attachment.created_at.desc()).all()
    return [AttachmentOut.from_orm(a) for a in attachments]


@router.post("/api/leads/{lead_id}/attachments")
def upload_attachment(lead_id: UUID, body: AttachmentUpload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Mode B: Google Drive link
    if body.drive_url:
        if not body.drive_url.startswith("https://drive.google.com"):
            raise HTTPException(status_code=400, detail="只接受 drive.google.com 的連結")
        filename = body.drive_name or "Google Drive 連結"
        attachment = Attachment(
            lead_id=lead_id,
            filename=filename,
            file_size=None,
            file_type=None,
            file_data=None,
            drive_url=body.drive_url,
            drive_name=body.drive_name,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return AttachmentOut.from_orm(attachment)

    # Mode A: file upload
    if not body.file_data:
        raise HTTPException(status_code=400, detail="請提供 file_data 或 drive_url")

    try:
        file_bytes = base64.b64decode(body.file_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    attachment = Attachment(
        lead_id=lead_id,
        filename=body.filename or "unnamed",
        file_size=len(file_bytes),
        file_type=body.file_type,
        file_data=body.file_data,
        drive_url=None,
        drive_name=None,
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return AttachmentOut.from_orm(attachment)


@router.get("/api/attachments/{attachment_id}/download")
def download_attachment(attachment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if attachment.drive_url:
        raise HTTPException(status_code=400, detail="This is a Drive link, not a downloadable file")

    try:
        file_bytes = base64.b64decode(attachment.file_data)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decode file data")

    media_type = attachment.file_type or "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )


@router.delete("/api/attachments/{attachment_id}")
def delete_attachment(attachment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    db.delete(attachment)
    db.commit()
    return {"message": "deleted"}
