import os
import json
import time
from datetime import datetime, timedelta
from utils import now_tw
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
import google.generativeai as genai
from database import get_db
from models import User, Lead, LeadActivity, LeadStatus, ActivityType, UserRole
from schemas import StatsOverview, SalesStat, FunnelStage
from auth import get_current_user, require_admin, get_visible_user_ids

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_suggestion_cache: dict = {"ts": 0, "data": []}
_pipeline_health_cache: dict = {"ts": 0, "data": ""}

router = APIRouter(prefix="/api/stats", tags=["stats"])

FUNNEL_ORDER = ["new", "contacted", "replied", "meeting_scheduled", "won", "lost"]


@router.get("/overview", response_model=StatsOverview)
def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Lead)
    visible_ids = get_visible_user_ids(current_user, db)
    if visible_ids is not None:
        q = q.filter(Lead.assigned_to.in_(visible_ids))

    total = q.count()
    counts = {s.value: 0 for s in LeadStatus}
    for row in q.with_entities(Lead.status, func.count()).group_by(Lead.status).all():
        counts[row[0].value] = row[1]

    week_ago = now_tw() - timedelta(days=7)
    email_q = db.query(LeadActivity).filter(
        LeadActivity.type == ActivityType.email_sent,
        LeadActivity.created_at >= week_ago,
    )
    if visible_ids is not None:
        email_q = email_q.filter(LeadActivity.created_by.in_(visible_ids))

    return StatsOverview(
        total_leads=total,
        new=counts["new"],
        contacted=counts["contacted"],
        replied=counts["replied"],
        meeting_scheduled=counts["meeting_scheduled"],
        won=counts["won"],
        lost=counts["lost"],
        emails_sent_this_week=email_q.count(),
    )


@router.get("/by_sales", response_model=List[SalesStat])
def by_sales(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = db.query(User).filter(User.role == UserRole.sales).all()
    result = []
    for user in users:
        total = db.query(Lead).filter(Lead.assigned_to == user.id).count()
        won = db.query(Lead).filter(Lead.assigned_to == user.id, Lead.status == LeadStatus.won).count()
        contacted = db.query(Lead).filter(
            Lead.assigned_to == user.id,
            Lead.status.in_([LeadStatus.contacted, LeadStatus.replied, LeadStatus.meeting_scheduled, LeadStatus.won])
        ).count()
        replied = db.query(Lead).filter(
            Lead.assigned_to == user.id,
            Lead.status.in_([LeadStatus.replied, LeadStatus.meeting_scheduled, LeadStatus.won])
        ).count()
        contact_rate = round(contacted / total * 100, 1) if total > 0 else 0.0
        reply_rate = round(replied / contacted * 100, 1) if contacted > 0 else 0.0
        result.append(SalesStat(
            user_id=user.id, name=user.name,
            total=total, won=won, contacted=contacted,
            replied=replied, contact_rate=contact_rate, reply_rate=reply_rate,
        ))
    return sorted(result, key=lambda x: x.won, reverse=True)


@router.get("/funnel", response_model=List[FunnelStage])
def funnel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Lead.status, func.count()).group_by(Lead.status)
    visible_ids = get_visible_user_ids(current_user, db)
    if visible_ids is not None:
        q = q.filter(Lead.assigned_to.in_(visible_ids))
    raw = {row[0].value: row[1] for row in q.all()}
    return [FunnelStage(status=s, count=raw.get(s, 0)) for s in FUNNEL_ORDER]


@router.get("/trend")
def trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """最近 14 天每日新增名單數 + 發信數"""
    visible_ids = get_visible_user_ids(current_user, db)
    result = []
    for i in range(13, -1, -1):
        day_start = now_tw().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        lq = db.query(Lead).filter(Lead.created_at >= day_start, Lead.created_at < day_end)
        eq = db.query(LeadActivity).filter(
            LeadActivity.type == ActivityType.email_sent,
            LeadActivity.created_at >= day_start,
            LeadActivity.created_at < day_end,
        )
        if visible_ids is not None:
            lq = lq.filter(Lead.assigned_to.in_(visible_ids))
            eq = eq.filter(LeadActivity.created_by.in_(visible_ids))
        result.append({
            "date": day_start.strftime("%m/%d"),
            "new_leads": lq.count(),
            "emails_sent": eq.count(),
        })
    return result


@router.get("/stale_leads")
def stale_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """超過 7 天未有 activity 的 leads（前 10 筆）"""
    threshold = now_tw() - timedelta(days=7)
    active_statuses = [LeadStatus.contacted, LeadStatus.replied, LeadStatus.meeting_scheduled, LeadStatus.new]
    q = db.query(Lead).filter(Lead.status.in_(active_statuses))
    visible_ids = get_visible_user_ids(current_user, db)
    if visible_ids is not None:
        q = q.filter(Lead.assigned_to.in_(visible_ids))

    stale = []
    for lead in q.order_by(Lead.updated_at).limit(50).all():
        last_act = db.query(LeadActivity).filter(
            LeadActivity.lead_id == lead.id
        ).order_by(LeadActivity.created_at.desc()).first()
        last_date = last_act.created_at if last_act else lead.created_at
        if last_date < threshold:
            stale.append({
                "id": str(lead.id),
                "company_name": lead.company_name,
                "status": lead.status.value,
                "last_activity": last_date.isoformat(),
                "days_stale": (now_tw() - last_date).days,
            })
        if len(stale) >= 10:
            break
    return stale


@router.get("/ai_suggestions")
def ai_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    refresh: bool = False,
):
    """AI 今日行動建議（1 小時 cache）"""
    global _suggestion_cache
    if not refresh and time.time() - _suggestion_cache["ts"] < 3600:
        return {"suggestions": _suggestion_cache["data"]}

    # Gather context
    threshold = now_tw() - timedelta(days=7)
    total = db.query(Lead).count()
    replied = db.query(Lead).filter(Lead.status == LeadStatus.replied).count()
    stale_count = 0
    for lead in db.query(Lead).filter(Lead.status.in_([LeadStatus.contacted, LeadStatus.replied])).all():
        last = db.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).order_by(LeadActivity.created_at.desc()).first()
        if not last or last.created_at < threshold:
            stale_count += 1
    unassigned = db.query(Lead).filter(Lead.assigned_to == None, Lead.status == LeadStatus.new).count()

    if not GEMINI_API_KEY:
        suggestions = ["請設定 GEMINI_API_KEY 以啟用 AI 建議功能"]
    else:
        prompt = f"""你是數位行銷業務主管助理，根據以下數據給出今日行動建議（繁體中文，3-5 條，每條一行，用「•」開頭）：
- 總名單數：{total}
- 有回覆但未約訪：{replied} 筆
- 超過 7 天未跟進：{stale_count} 筆
- 新名單未指派業務：{unassigned} 筆

給出具體、可執行的今日行動建議："""
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")
            resp = model.generate_content(prompt)
            lines = [l.strip() for l in resp.text.strip().split("\n") if l.strip().startswith("•")]
            suggestions = [l.lstrip("•").strip() for l in lines] or [resp.text.strip()]
        except Exception as e:
            suggestions = [f"AI 建議生成失敗：{str(e)}"]

    _suggestion_cache = {"ts": time.time(), "data": suggestions}
    return {"suggestions": suggestions}


@router.get("/pipeline_health")
def pipeline_health_cached(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    refresh: bool = False,
):
    """Return Gemini pipeline health report (1hr cache)."""
    global _pipeline_health_cache
    if not refresh and time.time() - _pipeline_health_cache["ts"] < 3600 and _pipeline_health_cache["data"]:
        return {"report": _pipeline_health_cache["data"]}

    if not GEMINI_API_KEY:
        return {"report": "請設定 GEMINI_API_KEY 以啟用 Pipeline 健診功能"}

    from sqlalchemy import func as sqlfunc
    import json as jsonlib

    total = db.query(Lead).count()
    by_status = {}
    for row in db.query(Lead.status, sqlfunc.count()).group_by(Lead.status).all():
        by_status[row[0].value] = row[1]

    week_ago = now_tw() - timedelta(days=7)
    emails_week = db.query(LeadActivity).filter(
        LeadActivity.type == ActivityType.email_sent,
        LeadActivity.created_at >= week_ago,
    ).count()

    stale_threshold = now_tw() - timedelta(days=7)
    stale_count = 0
    for lead in db.query(Lead).filter(Lead.status.in_([LeadStatus.contacted, LeadStatus.replied])).all():
        last = db.query(LeadActivity).filter(
            LeadActivity.lead_id == lead.id
        ).order_by(LeadActivity.created_at.desc()).first()
        if not last or last.created_at < stale_threshold:
            stale_count += 1

    prompt = f"""你是一位資深 B2B 業務顧問。請根據以下 Pipeline 數據，生成一份繁體中文的 Markdown 健診報告：

## Pipeline 數據
- 總名單數：{total}
- 各狀態分佈：{jsonlib.dumps(by_status, ensure_ascii=False)}
- 本週發信數：{emails_week}
- 超過7天未跟進：{stale_count} 筆

## 報告要求
請用 Markdown 格式，包含：
1. **健康度評分**（0-100分 + 評語）
2. **關鍵風險**（條列）
3. **建議行動**（優先順序排列）
4. **本週重點任務**（3項）

保持專業、具體、可執行。字數約 300-500 字。"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(prompt)
        report = resp.text.strip()
    except Exception as e:
        report = f"健診分析失敗：{str(e)}"

    _pipeline_health_cache = {"ts": time.time(), "data": report}
    return {"report": report}
