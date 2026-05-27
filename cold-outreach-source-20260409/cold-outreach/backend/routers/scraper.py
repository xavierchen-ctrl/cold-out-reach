"""
Scraper router — 會展廠商爬取模組
Sources: TAITRA, MEET TAIPEI, TWAA, DMA, 104, 1111, Google Maps, 工商登記, Facebook, Shopee, Momo
策略: 模組化爬蟲 (scrapers/) + legacy parsers
"""

import asyncio
import importlib
import json
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import User, Lead, LeadStatus, ScraperJob, ScraperJobStatus, UserRole
from schemas import ScraperRunRequest, ScraperJobOut, ScraperImportRequest, ScrapedCompany
from auth import get_current_user, require_admin_or_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scraper", tags=["scraper"])

# ── Sources config (新架構：模組化爬蟲) ─────────────────────────────────────────
# 格式: source_key -> (module_path, default_url)
# module_path 為 scrapers/ 下的模組，None 表示使用 legacy parser

SOURCES = {
    "apollo":          ("scrapers.apollo",      "apollo_search"),
    "lusha":           ("scrapers.lusha",       "lusha_enrich"),
    "job_104":         ("scrapers.job_boards",  "https://www.104.com.tw/jobs/search/api/jobs?keyword=數位行銷"),
    "job_1111":        ("scrapers.job_boards",  "https://www.1111.com.tw/search/job?ks=數位行銷"),
    "custom_url":      ("scrapers.custom_url",  "https://"),
    "moeaic":          ("scrapers.moeaic",       "https://company.g0v.tw"),
    "exhibition":      ("scrapers.exhibition",    "https://exh.taitra.org.tw"),
    "real_estate_591": ("scrapers.real_estate",   "https://newhouse.591.com.tw"),
    "ecommerce":       ("scrapers.ecommerce",     "shopee_search"),
}

DEFAULT_URLS = {k: v[1] for k, v in SOURCES.items()}
VALID_SOURCES = set(SOURCES.keys())

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _deduplicate(companies: List[ScrapedCompany]) -> List[ScrapedCompany]:
    seen = set()
    result = []
    for c in companies:
        key = c.company_name.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(c)
    return result



async def _run_scrape_module(source: str, url: str, keyword: str = None, industry: str = None, limit: int = 100) -> List[dict]:
    """動態 import scrapers/ 模組並呼叫 scrape(url)"""
    module_path = SOURCES[source][0]
    module = importlib.import_module(module_path)
    result = await module.scrape(url, keyword=keyword, industry=industry, limit=limit)
    # 統一格式：確保必要欄位存在
    normalized = []
    for item in result:
        normalized.append({
            "company_name": item.get("company_name", ""),
            "contact_name": item.get("contact_name"),
            "email": item.get("email"),
            "phone": item.get("phone"),
            "website": item.get("website"),
            "industry": item.get("industry"),
            "city": item.get("city"),
            "company_size": item.get("company_size"),
            "source": item.get("source", source),
            "source_url": item.get("source_url"),
            "notes": item.get("notes"),
        })
    return normalized


# ── Background task ────────────────────────────────────────────────────────────

SCRAPE_TIMEOUT_SECONDS = 600  # 10 分鐘上限


async def _run_scrape(job_id: str, source: str, url: str, keyword: str = None, industry: str = None, limit: int = 100):
    db = SessionLocal()
    try:
        job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
        if not job:
            return
        job.status = ScraperJobStatus.running
        job.updated_at = datetime.utcnow()
        db.commit()

        try:
            companies_dicts = await asyncio.wait_for(
                _run_scrape_module(source, url, keyword=keyword, industry=industry, limit=limit),
                timeout=SCRAPE_TIMEOUT_SECONDS,
            )
            job.result_json = json.dumps(companies_dicts, ensure_ascii=False)
            job.status = ScraperJobStatus.done
            job.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Scrape job {job_id} done: {len(companies_dicts)} companies")
        except asyncio.TimeoutError:
            job.status = ScraperJobStatus.failed
            job.error_msg = f"逾時（超過 {SCRAPE_TIMEOUT_SECONDS // 60} 分鐘）"
            job.updated_at = datetime.utcnow()
            db.commit()
            logger.warning(f"Scrape job {job_id} timed out after {SCRAPE_TIMEOUT_SECONDS}s")
        except Exception as e:
            job.status = ScraperJobStatus.failed
            job.error_msg = str(e)
            job.updated_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        try:
            job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
            if job:
                job.status = ScraperJobStatus.failed
                job.error_msg = str(e)
                job.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ── API Endpoints ──────────────────────────────────────────────────────────────

import os as _os

@router.get("/check-env")
def check_env(_: User = Depends(get_current_user)):
    """診斷：確認各爬蟲 API key 是否已設定（只顯示是否存在，不顯示值）"""
    return {
        "APOLLO_API_KEY":    bool(_os.getenv("APOLLO_API_KEY")),
        "GEMINI_API_KEY":    bool(_os.getenv("GEMINI_API_KEY")),
        "DATABASE_URL":      bool(_os.getenv("DATABASE_URL")),
    }


@router.post("/run", response_model=ScraperJobOut)
async def run_scrape(
    body: ScraperRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.sales:
        raise HTTPException(status_code=403, detail="Sales cannot use scraper")
    if body.source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source. Valid: {list(VALID_SOURCES)}")

    url = body.url or DEFAULT_URLS[body.source]

    # 把 keyword 寫進 url 讓 job 記錄可見
    if body.keyword and "keyword=" not in url:
        import urllib.parse
        url = url + ("&" if "?" in url else "?") + "keyword=" + urllib.parse.quote(body.keyword)

    job = ScraperJob(source=body.source, url=url, status=ScraperJobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = str(job.id)
    asyncio.create_task(_run_scrape(job_id, body.source, url,
                                    keyword=body.keyword, industry=body.industry,
                                    limit=body.limit or 100))

    return _job_to_out(job)


@router.get("/jobs", response_model=List[ScraperJobOut])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs = db.query(ScraperJob).order_by(ScraperJob.created_at.desc()).limit(50).all()
    return [_job_to_out(j) for j in jobs]


@router.get("/preview/{job_id}")
def preview_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != ScraperJobStatus.done:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}, not done yet")
    companies = json.loads(job.result_json or "[]")
    return {"count": len(companies), "companies": companies}


@router.post("/import/{job_id}")
def import_job(
    job_id: UUID,
    body: ScraperImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != ScraperJobStatus.done:
        raise HTTPException(status_code=400, detail="Job not done")

    companies = json.loads(job.result_json or "[]")
    source_label = f"exhibition:{job.source}"
    assigned = body.assigned_to or current_user.id

    # 只匯入有 email 的
    if body.email_only:
        companies = [c for c in companies if c.get("email")]

    created = 0
    skipped = 0
    for c in companies:
        name = c.get("company_name", "").strip()
        if not name:
            continue
        # Dedup: skip if same company_name + source already exists
        existing = db.query(Lead).filter(
            Lead.company_name == name,
            Lead.source == source_label,
        ).first()
        if existing:
            # 已存在：補填空白欄位（不覆蓋有值的）
            updated = False
            for field, val in [
                ("email", c.get("email")),
                ("phone", c.get("phone")),
                ("contact_name", c.get("contact_name")),
                ("title", c.get("title")),
                ("website", c.get("website")),
                ("city", c.get("city")),
                ("company_size", c.get("company_size")),
            ]:
                if val and not getattr(existing, field, None):
                    setattr(existing, field, val)
                    updated = True
            if updated:
                created += 1
            else:
                skipped += 1
            continue
        lead = Lead(
            company_name=name,
            contact_name=c.get("contact_name"),
            title=c.get("title"),
            email=c.get("email"),
            phone=c.get("phone"),
            website=c.get("website"),
            industry=c.get("industry", "數位行銷"),
            city=c.get("city"),
            company_size=c.get("company_size"),
            source=source_label,
            assigned_to=assigned,
            status=LeadStatus.new,
            notes=c.get("notes"),
        )
        db.add(lead)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped}


# ── Helper ─────────────────────────────────────────────────────────────────────

def _job_to_out(job: ScraperJob) -> ScraperJobOut:
    count = None
    if job.result_json:
        try:
            count = len(json.loads(job.result_json))
        except Exception:
            pass
    return ScraperJobOut(
        id=job.id,
        source=job.source,
        url=job.url,
        status=job.status,
        count=count,
        error_msg=job.error_msg,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
