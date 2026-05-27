"""Cadence 波段引擎 — 多管道跟進序列管理."""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import (
    User, Lead, Cadence, CadenceEnrollment, CadenceStepLog, LeadActivity, ActivityType
)

router = APIRouter(prefix="/api/cadences", tags=["cadences"])


def _cadence_to_dict(c: Cadence, db: Session) -> dict:
    enrollment_count = db.query(CadenceEnrollment).filter(
        CadenceEnrollment.cadence_id == c.id
    ).count()
    steps = c.steps or []
    return {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "steps": steps,
        "step_count": len(steps),
        "enrollment_count": enrollment_count,
        "created_by": str(c.created_by) if c.created_by else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _enrollment_to_dict(e: CadenceEnrollment) -> dict:
    lead = e.lead
    cadence = e.cadence
    steps = cadence.steps or [] if cadence else []
    total_steps = len(steps)

    return {
        "id": str(e.id),
        "cadence_id": str(e.cadence_id),
        "cadence_name": cadence.name if cadence else None,
        "lead_id": str(e.lead_id),
        "company_name": lead.company_name if lead else None,
        "contact_name": lead.contact_name if lead else None,
        "email": lead.email if lead else None,
        "current_step": e.current_step,
        "total_steps": total_steps,
        "status": e.status,
        "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
        "next_action_at": e.next_action_at.isoformat() if e.next_action_at else None,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        "current_step_info": steps[e.current_step] if e.current_step < total_steps else None,
        "step_logs": [
            {
                "id": str(log.id),
                "step_index": log.step_index,
                "step_type": log.step_type,
                "status": log.status,
                "note": log.note,
                "executed_at": log.executed_at.isoformat() if log.executed_at else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in e.step_logs
        ],
    }


def _compute_next_action_at(cadence: Cadence, step_index: int, base: datetime) -> Optional[datetime]:
    steps = cadence.steps or []
    if step_index >= len(steps):
        return None
    step = steps[step_index]
    day_offset = step.get("day", 1)
    return base + timedelta(days=day_offset)


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_cadences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cadences = db.query(Cadence).order_by(Cadence.created_at.desc()).all()
    return [_cadence_to_dict(c, db) for c in cadences]


@router.post("")
def create_cadence(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.get("name"):
        raise HTTPException(status_code=400, detail="name required")
    cadence = Cadence(
        name=body["name"],
        description=body.get("description"),
        steps=body.get("steps", []),
        created_by=current_user.id,
    )
    db.add(cadence)
    db.commit()
    db.refresh(cadence)
    return _cadence_to_dict(cadence, db)


@router.get("/due")
def get_due_steps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active enrollments where next_action_at <= now."""
    now = datetime.utcnow()
    enrollments = (
        db.query(CadenceEnrollment)
        .filter(
            CadenceEnrollment.status == "active",
            CadenceEnrollment.next_action_at <= now,
        )
        .all()
    )
    return [_enrollment_to_dict(e) for e in enrollments]


@router.get("/{cadence_id}")
def get_cadence(
    cadence_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(Cadence).filter(Cadence.id == cadence_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cadence not found")
    return _cadence_to_dict(c, db)


@router.put("/{cadence_id}")
def update_cadence(
    cadence_id: UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(Cadence).filter(Cadence.id == cadence_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cadence not found")
    for field in ["name", "description", "steps"]:
        if field in body:
            setattr(c, field, body[field])
    db.commit()
    db.refresh(c)
    return _cadence_to_dict(c, db)


@router.delete("/{cadence_id}")
def delete_cadence(
    cadence_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = db.query(Cadence).filter(Cadence.id == cadence_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cadence not found")
    db.delete(c)
    db.commit()
    return {"message": "deleted"}


# ── Enrollment ────────────────────────────────────────────────────────────────

@router.post("/{cadence_id}/enroll")
def enroll_leads(
    cadence_id: UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll leads into a cadence. body: {"lead_ids": [...]}"""
    c = db.query(Cadence).filter(Cadence.id == cadence_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cadence not found")

    lead_ids = body.get("lead_ids", [])
    if not lead_ids:
        raise HTTPException(status_code=400, detail="lead_ids required")

    enrolled = []
    skipped = []
    steps = c.steps or []

    for lid in lead_ids:
        # Check if already enrolled and active
        existing = db.query(CadenceEnrollment).filter(
            CadenceEnrollment.cadence_id == cadence_id,
            CadenceEnrollment.lead_id == lid,
            CadenceEnrollment.status == "active",
        ).first()
        if existing:
            skipped.append(lid)
            continue

        now = datetime.utcnow()
        next_at = None
        if steps:
            day_offset = steps[0].get("day", 1)
            next_at = now + timedelta(days=day_offset - 1)  # day 1 = today

        enrollment = CadenceEnrollment(
            cadence_id=cadence_id,
            lead_id=lid,
            current_step=0,
            status="active",
            enrolled_at=now,
            next_action_at=next_at,
        )
        db.add(enrollment)
        enrolled.append(lid)

    db.commit()
    return {"enrolled": len(enrolled), "skipped": len(skipped)}


@router.get("/{cadence_id}/enrollments")
def list_enrollments(
    cadence_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enrollments = (
        db.query(CadenceEnrollment)
        .filter(CadenceEnrollment.cadence_id == cadence_id)
        .all()
    )
    return [_enrollment_to_dict(e) for e in enrollments]


# ── Enrollment actions ────────────────────────────────────────────────────────

@router.post("/enrollments/{enrollment_id}/advance")
def advance_enrollment(
    enrollment_id: UUID,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark current step done and advance to next."""
    e = db.query(CadenceEnrollment).filter(CadenceEnrollment.id == enrollment_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    cadence = e.cadence
    steps = cadence.steps or []

    # Log current step as done
    log = CadenceStepLog(
        enrollment_id=e.id,
        step_index=e.current_step,
        step_type=steps[e.current_step]["type"] if e.current_step < len(steps) else "unknown",
        status="done",
        note=body.get("note"),
        executed_at=datetime.utcnow(),
    )
    db.add(log)

    # Advance
    e.current_step += 1
    if e.current_step >= len(steps):
        e.status = "completed"
        e.completed_at = datetime.utcnow()
        e.next_action_at = None
    else:
        next_step = steps[e.current_step]
        base = e.enrolled_at or datetime.utcnow()
        day_offset = next_step.get("day", e.current_step + 1)
        e.next_action_at = base + timedelta(days=day_offset - 1)

    # Add activity to lead
    if e.lead_id:
        act = LeadActivity(
            lead_id=e.lead_id,
            type=ActivityType.email_sent if (e.current_step > 0 and steps[e.current_step - 1].get("type") == "email") else ActivityType.call_note,
            content=f"[Cadence: {cadence.name}] Step {e.current_step} 完成",
            created_by=current_user.id,
        )
        db.add(act)

    db.commit()
    db.refresh(e)
    return _enrollment_to_dict(e)


@router.post("/enrollments/{enrollment_id}/skip_step")
def skip_step(
    enrollment_id: UUID,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Skip current step and advance."""
    e = db.query(CadenceEnrollment).filter(CadenceEnrollment.id == enrollment_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    cadence = e.cadence
    steps = cadence.steps or []

    # Log as skipped
    log = CadenceStepLog(
        enrollment_id=e.id,
        step_index=e.current_step,
        step_type=steps[e.current_step]["type"] if e.current_step < len(steps) else "unknown",
        status="skipped",
        note=body.get("note"),
        executed_at=datetime.utcnow(),
    )
    db.add(log)

    e.current_step += 1
    if e.current_step >= len(steps):
        e.status = "completed"
        e.completed_at = datetime.utcnow()
        e.next_action_at = None
    else:
        next_step = steps[e.current_step]
        base = e.enrolled_at or datetime.utcnow()
        day_offset = next_step.get("day", e.current_step + 1)
        e.next_action_at = base + timedelta(days=day_offset - 1)

    db.commit()
    db.refresh(e)
    return _enrollment_to_dict(e)


@router.post("/enrollments/{enrollment_id}/pause")
def pause_enrollment(
    enrollment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    e = db.query(CadenceEnrollment).filter(CadenceEnrollment.id == enrollment_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    e.status = "paused"
    db.commit()
    return {"status": "paused"}


@router.post("/enrollments/{enrollment_id}/resume")
def resume_enrollment(
    enrollment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    e = db.query(CadenceEnrollment).filter(CadenceEnrollment.id == enrollment_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    e.status = "active"
    db.commit()
    return {"status": "active"}


# ── Lead-specific cadence enrollments ────────────────────────────────────────

@router.get("/lead/{lead_id}")
def get_lead_cadences(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all cadence enrollments for a specific lead."""
    enrollments = (
        db.query(CadenceEnrollment)
        .filter(CadenceEnrollment.lead_id == lead_id)
        .all()
    )
    return [_enrollment_to_dict(e) for e in enrollments]
