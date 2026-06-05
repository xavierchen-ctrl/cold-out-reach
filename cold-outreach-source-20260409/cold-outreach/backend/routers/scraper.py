"""
Scraper router — 會展廠商爬取模組
Sources: TAITRA, MEET TAIPEI, TWAA, DMA, 104, 1111, Google Maps, 工商登記, Facebook, Shopee, Momo
策略: 模組化爬蟲 (scrapers/) + legacy parsers
"""

import asyncio
import importlib
import json
import logging
from typing import List
from uuid import UUID
from utils import now_tw

import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import User, Lead, LeadStatus, ScraperJob, ScraperJobStatus, UserRole
from schemas import ScraperRunRequest, ScraperJobOut, ScraperImportRequest, ScrapedCompany
from auth import get_current_user

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
    "gemini_search":   ("scrapers.gemini_search", "gemini_search"),
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



async def _run_scrape_module(source: str, url: str, keyword: str = None, industry: str = None, limit: int = 100, threads_cookie: str = None) -> List[dict]:
    """動態 import scrapers/ 模組並呼叫 scrape(url)"""
    module_path = SOURCES[source][0]
    module = importlib.import_module(module_path)
    extra = {}
    if threads_cookie and source in ("threads", "threads_posts"):
        extra["cookies_str"] = threads_cookie
    result = await module.scrape(url, keyword=keyword, industry=industry, limit=limit, **extra)
    # 統一格式：確保必要欄位存在
    normalized = []
    for item in result:
        entry = {
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
        }
        # 保留 threads_posts 專屬欄位
        for extra_key in ("post_text", "likes", "reposts", "replies"):
            if extra_key in item:
                entry[extra_key] = item[extra_key]
        normalized.append(entry)
    return normalized


# ── Background task ────────────────────────────────────────────────────────────

SCRAPE_TIMEOUT_SECONDS = 600  # 10 分鐘上限


async def _run_scrape(job_id: str, source: str, url: str, keyword: str = None, industry: str = None, limit: int = 100, threads_cookie: str = None):
    db = SessionLocal()
    try:
        job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
        if not job:
            return
        job.status = ScraperJobStatus.running
        job.updated_at = now_tw()
        db.commit()

        try:
            companies_dicts = await asyncio.wait_for(
                _run_scrape_module(source, url, keyword=keyword, industry=industry, limit=limit, threads_cookie=threads_cookie),
                timeout=SCRAPE_TIMEOUT_SECONDS,
            )
            job.result_json = json.dumps(companies_dicts, ensure_ascii=False)
            job.status = ScraperJobStatus.done
            job.updated_at = now_tw()
            db.commit()
            logger.info(f"Scrape job {job_id} done: {len(companies_dicts)} companies")
        except asyncio.TimeoutError:
            job.status = ScraperJobStatus.failed
            job.error_msg = f"逾時（超過 {SCRAPE_TIMEOUT_SECONDS // 60} 分鐘）"
            job.updated_at = now_tw()
            db.commit()
            logger.warning(f"Scrape job {job_id} timed out after {SCRAPE_TIMEOUT_SECONDS}s")
        except Exception as e:
            job.status = ScraperJobStatus.failed
            job.error_msg = str(e)
            job.updated_at = now_tw()
            db.commit()

    except Exception as e:
        try:
            job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
            if job:
                job.status = ScraperJobStatus.failed
                job.error_msg = str(e)
                job.updated_at = now_tw()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ── API Endpoints ──────────────────────────────────────────────────────────────

import os as _os
import urllib.parse as _urlparse
from bs4 import BeautifulSoup as _BS
from pydantic import BaseModel as _BM
from typing import Optional as _Opt


class _JobFieldUpdate(_BM):
    index: int
    field: str
    value: _Opt[str] = None


_WEBSITE_BLACKLIST = {
    'facebook.com', 'instagram.com', 'twitter.com', 'x.com', 'linkedin.com',
    'youtube.com', 'threads.net', 'google.com', 'wikipedia.org', 'yahoo.com',
    'line.me', 'tiktok.com', 'amazon.com', 'shopee.tw', 'shopee.com',
    # 求職網站
    '104.com.tw', '1111.com.tw', '518.com.tw', 'yes123.com.tw',
    'cake.me', 'cakeresume.com', 'yourator.co', 'jobs.com.tw',
    # 商業資料庫 / 公司查詢
    'businessgo.com.tw', 'gcis.nat.gov.tw', 'findbiz.nat.gov.tw',
    'company.g0v.tw', 'moeaic.gov.tw', 'findcompany.com.tw',
    'twincn.com', 'tycns.com.tw', 'bizopen.moeaic.gov.tw',
}

_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def _is_good_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    domain = _urlparse.urlparse(url).netloc.lower().lstrip("www.")
    return bool(domain) and not any(bl in domain for bl in _WEBSITE_BLACKLIST)


async def _search_ddg(client, query: str) -> _Opt[str]:
    """DuckDuckGo HTML 搜尋，回傳第一個合法網址"""
    resp = await client.get(
        f"https://html.duckduckgo.com/html/?q={_urlparse.quote(query)}",
        timeout=12,
    )
    soup = _BS(resp.text, "lxml")
    for a in soup.select("a.result__url"):
        href = a.get("href", "")
        params = _urlparse.parse_qs(_urlparse.urlparse(href).query)
        url = params.get("uddg", [""])[0]
        if not url:
            text = a.get_text(strip=True)
            url = ("https://" + text) if text and not text.startswith("http") else text
        if not url.startswith("http"):
            url = "https://" + url
        if _is_good_url(url):
            return url
    return None


async def _search_bing(client, query: str) -> _Opt[str]:
    """Bing 搜尋備援，回傳第一個合法網址"""
    resp = await client.get(
        f"https://www.bing.com/search?q={_urlparse.quote(query)}",
        timeout=12,
    )
    soup = _BS(resp.text, "lxml")
    for a in soup.select("li.b_algo h2 a, li.b_algo .b_title a"):
        url = a.get("href", "")
        if _is_good_url(url):
            return url
    return None


async def _guess_domain(client, company_name: str) -> _Opt[str]:
    """從公司名稱猜測域名並用 HTTP 驗證是否存在"""
    import re as _re
    # 去掉常見後綴，只留品牌關鍵字
    stripped = _re.sub(
        r'\b(CO\.?,?\s*LTD\.?|INC\.?|CORP\.?|LLC\.?|LIMITED|CORPORATION|COMPANY'
        r'|TAIWAN|TECHNOLOGY|TECH|ELECTRONICS|SYSTEM|SYSTEMS|SOLUTIONS|INTERNATIONAL|GLOBAL)\b',
        '', company_name, flags=_re.IGNORECASE,
    )
    words = [w.lower() for w in _re.findall(r'[A-Za-z]+', stripped) if len(w) > 1]
    if not words:
        return None

    candidates = []
    candidates.append(f"https://www.{words[0]}.com.tw")
    candidates.append(f"https://www.{words[0]}.tw")
    candidates.append(f"https://www.{words[0]}.com")
    if len(words) >= 2:
        merged = words[0] + words[1]
        candidates.append(f"https://www.{merged}.com.tw")
        candidates.append(f"https://www.{merged}.tw")
        candidates.append(f"https://www.{merged}.com")

    for url in candidates:
        try:
            resp = await client.head(url, timeout=6, follow_redirects=True)
            if resp.status_code < 400:
                return str(resp.url)
        except Exception:
            pass
    return None


@router.get("/find-website")
async def find_website_for_company(
    q: str,
    current_user: User = Depends(get_current_user),
):
    """根據公司名稱搜尋官方網站（DuckDuckGo → Bing → 域名猜測）"""
    import re as _re

    is_english = bool(_re.match(r'^[A-Za-z0-9\s\.\,\-\&\(\)\/]+$', q.strip()))

    clean_q = _re.sub(
        r'\b(CO\.?,?\s*LTD\.?|INC\.?|CORP\.?|LLC\.?|LIMITED|CORPORATION|COMPANY)\s*$',
        '', q, flags=_re.IGNORECASE,
    ).strip(' ,.')

    if is_english:
        candidates = [
            f"{clean_q} official website",
            f"{clean_q} taiwan",
            f"{q} official website",
        ]
    else:
        candidates = [f"{q} 官方網站", f"{q} 官網", q]

    found = None
    try:
        async with httpx.AsyncClient(
            headers=_SEARCH_HEADERS, follow_redirects=True
        ) as client:
            # 1. DuckDuckGo
            for search_q in candidates:
                found = await _search_ddg(client, search_q)
                if found:
                    break

            # 2. Bing 備援
            if not found:
                for search_q in candidates:
                    found = await _search_bing(client, search_q)
                    if found:
                        break

            # 3. 域名猜測（僅英文名稱）
            if not found and is_english:
                found = await _guess_domain(client, q)

    except Exception as e:
        logger.warning(f"find-website error for {q!r}: {e}")

    return {"website": found}


@router.patch("/jobs/{job_id}/update-field")
def update_job_field(
    job_id: UUID,
    body: _JobFieldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 job result_json 中特定索引的欄位值（前端即時補資料用）"""
    job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    companies = json.loads(job.result_json or "[]")
    if 0 <= body.index < len(companies):
        companies[body.index][body.field] = body.value
        job.result_json = json.dumps(companies, ensure_ascii=False)
        db.commit()
    return {"ok": True}

@router.get("/check-env")
def check_env():
    """診斷：確認各爬蟲 API key 是否已設定（只顯示 true/false，不顯示值）"""
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
    threads_cookie = current_user.threads_cookie if body.source in ("threads", "threads_posts") else None
    asyncio.create_task(_run_scrape(job_id, body.source, url,
                                    keyword=body.keyword, industry=body.industry,
                                    limit=body.limit or 100, threads_cookie=threads_cookie))

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

    # 只匯入勾選的項目（前端傳入原始索引列表）
    if body.indices is not None:
        idx_set = set(body.indices)
        companies = [c for i, c in enumerate(companies) if i in idx_set]

    created = 0
    skipped = 0
    for c in companies:
        name = c.get("company_name", "").strip()
        if not name:
            continue
        # Dedup: skip if same company_name already exists (regardless of source)
        existing = db.query(Lead).filter(
            Lead.company_name == name,
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
