import csv
import io
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User, Lead, LeadActivity, LeadStatus, ActivityType, UserRole, LeadTag, Tag, EmailOpen, EmailClick, CallLog, PendingLeadApproval
from schemas import LeadCreate, LeadUpdate, LeadStatusUpdate, LeadOut, ActivityOut
from auth import get_current_user, get_visible_user_ids

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _check_access(lead: Lead, user: User, db: Session):
    visible_ids = get_visible_user_ids(user, db)
    if visible_ids is not None and lead.assigned_to not in visible_ids:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("", response_model=List[LeadOut])
def list_leads(
    status: Optional[str] = Query(None),
    assigned_to: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),  # comma-separated tag names
    sort: Optional[str] = Query(None),  # "contact_first" = 有電話+email優先
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Lead)
    # All roles can see all leads; ownership is enforced at the detail level
    if status:
        q = q.filter(Lead.status == status)
    if assigned_to and current_user.role == UserRole.admin:
        q = q.filter(Lead.assigned_to == assigned_to)
    if search:
        like = f"%{search}%"
        q = q.filter(
            Lead.company_name.ilike(like) |
            Lead.contact_name.ilike(like) |
            Lead.email.ilike(like)
        )
    if tags:
        tag_names = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_names:
            # Filter leads that have ALL the specified tags
            for tag_name in tag_names:
                tag = db.query(Tag).filter(Tag.name == tag_name).first()
                if tag:
                    q = q.filter(
                        Lead.id.in_(
                            db.query(LeadTag.lead_id).filter(LeadTag.tag_id == tag.id)
                        )
                    )
    from sqlalchemy import case, and_
    if sort == "contact_first":
        # 有電話+email > 只有email > 只有電話 > 都沒有
        priority = case(
            (and_(Lead.phone.isnot(None), Lead.email.isnot(None)), 0),
            (and_(Lead.phone.is_(None), Lead.email.isnot(None)), 1),
            (and_(Lead.phone.isnot(None), Lead.email.is_(None)), 2),
            else_=3
        )
        q = q.order_by(priority, Lead.created_at.desc())
    else:
        q = q.order_by(Lead.created_at.desc())
    return q.offset(skip).limit(limit).all()


@router.post("")
def create_lead(
    body: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.sales:
        body.assigned_to = current_user.id

    # ── 同公司不同部門偵測 ──────────────────────────────────────────
    existing = db.query(Lead).filter(Lead.company_name.ilike(body.company_name)).all()
    if existing:
        new_dept = (body.department or "").strip().lower()
        same_dept_found = any((l.department or "").strip().lower() == new_dept for l in existing)
        if not same_dept_found:
            approval = PendingLeadApproval(
                submitted_by=current_user.id,
                lead_data=body.model_dump(mode="json"),
                conflict_company=body.company_name,
                conflict_lead_id=existing[0].id,
            )
            db.add(approval)
            db.commit()
            db.refresh(approval)
            existing_dept_display = existing[0].department or "（未填）"
            new_dept_display = body.department or "（未填）"
            return JSONResponse(
                status_code=202,
                content={
                    "pending_approval": True,
                    "approval_id": str(approval.id),
                    "message": (
                        f"「{body.company_name}」已有名單（部門：{existing_dept_display}），"
                        f"新增部門「{new_dept_display}」需送請小組長及 Ivy 審核，"
                        "核准後才會正式建立。"
                    ),
                },
            )
    # ── 無衝突，直接建立 ──────────────────────────────────────────
    lead = Lead(**body.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_access(lead, current_user, db)
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: UUID,
    body: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_access(lead, current_user, db)

    old_status = lead.status
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    if body.status and body.status != old_status:
        activity = LeadActivity(
            lead_id=lead.id,
            type=ActivityType.status_change,
            content=f"{old_status.value} → {body.status.value}",
            created_by=current_user.id,
        )
        db.add(activity)

    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(lead_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.sales:
        raise HTTPException(status_code=403, detail="Sales cannot delete leads")
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"message": "deleted"}


@router.patch("/{lead_id}/status", response_model=LeadOut)
def update_status(
    lead_id: UUID,
    body: LeadStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _check_access(lead, current_user, db)

    old_status = lead.status
    lead.status = body.status
    activity = LeadActivity(
        lead_id=lead.id,
        type=ActivityType.status_change,
        content=f"{old_status.value} → {body.status.value}",
        created_by=current_user.id,
    )
    db.add(activity)
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/recalc_engagement/all")
def recalc_engagement_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recalculate engagement score for all leads."""
    leads = db.query(Lead).all()
    updated = 0
    for lead in leads:
        _recalc_one(lead, db)
        updated += 1
    db.commit()
    return {"updated": updated}


@router.post("/{lead_id}/recalc_engagement")
def recalc_engagement(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recalculate engagement score for a single lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    _recalc_one(lead, db)
    db.commit()
    db.refresh(lead)
    return {"id": str(lead.id), "engagement_score": lead.engagement_score}


def _recalc_one(lead: Lead, db: Session):
    """Recalculate engagement score for a single lead object."""
    score = 0
    # Opens +10 each
    opens = db.query(EmailOpen).filter(EmailOpen.lead_id == lead.id).count()
    score += opens * 10
    # Clicks +20 each
    clicks = db.query(EmailClick).filter(EmailClick.lead_id == lead.id).count()
    score += clicks * 20
    # Replies +50
    if lead.status in ("replied", "meeting_scheduled", "won"):
        score += 50
    # Calls +30 for answered, +5 others
    calls = db.query(CallLog).filter(CallLog.lead_id == lead.id).all()
    for c in calls:
        score += 30 if c.outcome == "answered" else 5
    # Status progression +15
    activities = db.query(LeadActivity).filter(
        LeadActivity.lead_id == lead.id,
        LeadActivity.type == ActivityType.status_change,
    ).count()
    score += activities * 15
    lead.engagement_score = score


@router.get("/template")
def download_template(current_user: User = Depends(get_current_user)):
    """下載 Excel 匯入範本（含中文欄位名稱與範例資料）"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "名單範本"

    headers = ["公司名稱", "部門", "聯絡人", "職稱", "email", "電話", "產業", "城市", "公司規模", "來源"]
    header_fill = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # 標記必填欄位 (公司名稱)
    ws.cell(row=2, column=1, value="範例公司股份有限公司")
    ws.cell(row=2, column=2, value="行銷部")
    ws.cell(row=2, column=3, value="王小明")
    ws.cell(row=2, column=4, value="行銷總監")
    ws.cell(row=2, column=5, value="example@company.com")
    ws.cell(row=2, column=6, value="02-1234-5678")
    ws.cell(row=2, column=7, value="數位行銷")
    ws.cell(row=2, column=8, value="台北")
    ws.cell(row=2, column=9, value="50-100人")
    ws.cell(row=2, column=10, value="csv_import")

    # 欄位寬度
    col_widths = [25, 12, 12, 14, 28, 16, 14, 10, 12, 14]
    for col, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    # 備註行
    note_cell = ws.cell(row=3, column=1, value="※ 公司名稱為必填，其餘欄位選填")
    note_cell.font = Font(color="DC2626", italic=True)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="lead_template.xlsx"'},
    )


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    errors = []
    for i, row in enumerate(reader):
        try:
            company = row.get("company_name") or row.get("公司名稱") or row.get("company")
            if not company:
                errors.append(f"Row {i+2}: missing company_name")
                continue
            lead = Lead(
                company_name=company.strip(),
                department=(row.get("department") or row.get("部門") or "").strip() or None,
                contact_name=(row.get("contact_name") or row.get("聯絡人") or "").strip() or None,
                title=(row.get("title") or row.get("職稱") or "").strip() or None,
                email=(row.get("email") or row.get("Email") or "").strip() or None,
                phone=(row.get("phone") or row.get("電話") or "").strip() or None,
                industry=(row.get("industry") or row.get("產業") or "").strip() or None,
                city=(row.get("city") or row.get("城市") or "").strip() or None,
                company_size=(row.get("company_size") or row.get("公司規模") or "").strip() or None,
                source=(row.get("source") or row.get("來源") or "csv_import").strip(),
                assigned_to=current_user.id if current_user.role == UserRole.sales else None,
                status=LeadStatus.new,
            )
            db.add(lead)
            created += 1
        except Exception as e:
            errors.append(f"Row {i+2}: {str(e)}")

    db.commit()
    return {"created": created, "errors": errors}
