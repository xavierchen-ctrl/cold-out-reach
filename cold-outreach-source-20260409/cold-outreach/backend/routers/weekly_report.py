import os
from datetime import datetime, timedelta
from utils import now_tw
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import LeadActivity, Lead, LeadStatus, ActivityType, WeeklyReport
from auth import get_current_user
from models import User
import google.generativeai as genai

router = APIRouter(prefix="/api/reports", tags=["weekly_reports"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDXH1Rg-D3Txd7Yiod12Ykli2CzBwEbZbA")


def _get_week_stats(db: Session, week_start: datetime, week_end: datetime) -> dict:
    """Gather stats for a given week range."""
    emails_sent = (
        db.query(LeadActivity)
        .filter(
            LeadActivity.type == ActivityType.email_sent,
            LeadActivity.created_at >= week_start,
            LeadActivity.created_at < week_end,
        )
        .count()
    )
    
    replied = (
        db.query(Lead)
        .filter(
            Lead.status == LeadStatus.replied,
            Lead.updated_at >= week_start,
            Lead.updated_at < week_end,
        )
        .count()
    )
    
    won = (
        db.query(Lead)
        .filter(
            Lead.status == LeadStatus.won,
            Lead.updated_at >= week_start,
            Lead.updated_at < week_end,
        )
        .count()
    )
    
    new_leads = (
        db.query(Lead)
        .filter(
            Lead.created_at >= week_start,
            Lead.created_at < week_end,
        )
        .count()
    )
    
    return {
        "emails_sent": emails_sent,
        "replied": replied,
        "won": won,
        "new_leads": new_leads,
        "reply_rate": round((replied / emails_sent * 100) if emails_sent > 0 else 0, 1),
    }


@router.get("/weekly")
async def generate_weekly_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = now_tw()
    # This week: Monday to now
    days_since_monday = now.weekday()
    week_start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    
    # Last week
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start
    
    this_week = _get_week_stats(db, week_start, week_end)
    last_week = _get_week_stats(db, last_week_start, last_week_end)
    
    # Check if we have a cached report for this week
    existing = db.query(WeeklyReport).filter(
        WeeklyReport.week_start >= week_start,
        WeeklyReport.week_start < week_end,
    ).first()
    
    # Generate AI report
    prompt = f"""你是一位銷售分析師，請根據以下數據生成本週的銷售週報（Markdown 格式）：

## 本週數據（{week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}）
- 發信數：{this_week['emails_sent']} 封
- 回覆數：{this_week['replied']} 筆
- 成交數：{this_week['won']} 筆
- 新增名單：{this_week['new_leads']} 筆
- 回覆率：{this_week['reply_rate']}%

## 上週數據（對比）
- 發信數：{last_week['emails_sent']} 封
- 回覆數：{last_week['replied']} 筆
- 成交數：{last_week['won']} 筆
- 新增名單：{last_week['new_leads']} 筆
- 回覆率：{last_week['reply_rate']}%

請生成包含以下內容的週報：
1. **執行摘要**（2-3 句話）
2. **數據分析**（與上週對比，指出亮點和問題）
3. **下週建議**（具體可執行的 3 點建議）

風格：簡潔、有力、數據導向。"""
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        report_content = response.text
    except Exception as e:
        report_content = f"""# 本週銷售週報

## 執行摘要
本週共發送 {this_week['emails_sent']} 封郵件，獲得 {this_week['replied']} 次回覆，成交 {this_week['won']} 筆。

## 數據分析
- 發信數：{this_week['emails_sent']} 封（上週：{last_week['emails_sent']} 封）
- 回覆數：{this_week['replied']} 筆（上週：{last_week['replied']} 筆）
- 成交數：{this_week['won']} 筆（上週：{last_week['won']} 筆）
- 新增名單：{this_week['new_leads']} 筆（上週：{last_week['new_leads']} 筆）
- 回覆率：{this_week['reply_rate']}%

## 下週建議
1. 持續跟進尚未回覆的名單
2. 優化發信主旨以提升開信率
3. 重點追蹤高分名單

（AI 生成失敗，使用預設模板：{str(e)[:100]}）"""
    
    stats_snapshot = {"this_week": this_week, "last_week": last_week}
    
    if existing:
        existing.content = report_content
        existing.stats_snapshot = stats_snapshot
        db.commit()
        db.refresh(existing)
        report = existing
    else:
        report = WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            content=report_content,
            stats_snapshot=stats_snapshot,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
    
    return {
        "id": str(report.id),
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "content": report.content,
        "stats": stats_snapshot,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/weekly/history")
def get_weekly_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reports = db.query(WeeklyReport).order_by(WeeklyReport.week_start.desc()).limit(12).all()
    return [
        {
            "id": str(r.id),
            "week_start": r.week_start.isoformat(),
            "week_end": r.week_end.isoformat(),
            "stats": r.stats_snapshot,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/weekly/{report_id}")
def get_weekly_report(report_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from uuid import UUID
    try:
        uuid = UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report ID")
    report = db.query(WeeklyReport).filter(WeeklyReport.id == uuid).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": str(report.id),
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "content": report.content,
        "stats": report.stats_snapshot,
        "created_at": report.created_at.isoformat(),
    }


@router.post("/weekly/export_pdf")
async def export_pdf(report_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return HTML page optimized for browser print-to-PDF."""
    if report_id:
        from uuid import UUID
        try:
            uuid = UUID(report_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid report ID")
        report = db.query(WeeklyReport).filter(WeeklyReport.id == uuid).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        content = report.content
        week_start = report.week_start.strftime("%Y-%m-%d")
    else:
        content = "# 週報\n\n請先生成週報。"
        week_start = now_tw().strftime("%Y-%m-%d")
    
    # Convert markdown to simple HTML
    import re
    html_content = content
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = html_content.replace('\n', '<br>')
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>週報 {week_start}</title>
<style>
body {{ font-family: "Noto Sans TC", Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
h1, h2, h3 {{ color: #1e293b; }}
li {{ margin: 4px 0; }}
@media print {{ body {{ margin: 0; }} }}
</style>
</head>
<body>
{html_content}
<script>window.onload = function() {{ window.print(); }}</script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

