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
    # 產業公會 / 協會目錄
    'icaa.org.tw', 'icaa.tw', 'tca.org.tw', 'teema.org.tw',
    'taitra.org.tw', 'taiwantrade.com', 'taiwantrade.com.tw',
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


_TW_AREA3_SET = {'037', '038', '039', '049', '055', '056', '082', '083', '089'}
_TW_AREA2_7DIGIT = {'05', '06', '07', '08'}  # 2-digit area codes with 7-digit locals


def _fmt_phone_digits(digits: str) -> str:
    """將純數字字串（已開頭0，長度8-10）格式化為帶連字號的台灣電話"""
    if digits.startswith('09') and len(digits) == 10:
        return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 9:
        a3 = digits[:3]
        a2 = digits[:2]
        if a3 in _TW_AREA3_SET:
            return f"{a3}-{digits[3:6]}-{digits[6:]}"
        if a2 in _TW_AREA2_7DIGIT:
            return f"{a2}-{digits[2:5]}-{digits[5:]}"
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return digits


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


async def _search_google(client, query: str) -> _Opt[str]:
    """Google 搜尋備援，解析 /url?q= 重定向連結取得第一個合法官網"""
    import re as _re_g
    try:
        resp = await client.get(
            f"https://www.google.com/search?q={_urlparse.quote(query)}&hl=zh-TW&gl=tw&num=10",
            timeout=12,
        )
        # Google encodes organic result links as /url?q=https://...&sa=...
        for m in _re_g.finditer(r'/url\?q=(https?://[^&"\']+)', resp.text):
            url = _urlparse.unquote(m.group(1))
            if _is_good_url(url):
                return url
    except Exception:
        pass
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
    """根據公司名稱搜尋官方網站（DuckDuckGo → Bing → Google → 域名猜測）"""
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

            # 3. Google 備援
            if not found:
                for search_q in candidates:
                    found = await _search_google(client, search_q)
                    if found:
                        break

            # 4. 域名猜測（僅英文名稱）
            if not found and is_english:
                found = await _guess_domain(client, q)

    except Exception as e:
        logger.warning(f"find-website error for {q!r}: {e}")

    return {"website": found}


@router.get("/find-phone")
async def find_phone_for_company(
    q: str,
    website: _Opt[str] = None,
    current_user: User = Depends(get_current_user),
):
    """搜尋公司電話：先爬官網，再用 Gemini，再用 DuckDuckGo/Bing"""
    import re as _re
    import os as _os2

    _TW_PHONE = _re.compile(
        r'(?<!\d)'
        r'('
        r'0800[-\s]?\d{3}[-\s]?\d{3}'
        r'|0[2-9]\d?[-\s]?\d{3,4}[-\s]?\d{4}'
        r'|09\d{2}[-\s]?\d{3}[-\s]?\d{3}'
        r'|\(\d{2,3}\)\s*\d{3,4}[-\s]?\d{4}'    # (04)22794607 or (04) 2279-4607
        r')'
        r'(?!\d)'
    )

    # 0a. 台灣商業司 findbiz（先搜名稱取統編，再抓詳細頁電話）
    try:
        async with httpx.AsyncClient(headers=_SEARCH_HEADERS, follow_redirects=True, timeout=15) as client:
            list_url = f"https://findbiz.nat.gov.tw/fts/query/QueryList/queryList.do?qyFreedom={_urlparse.quote(q)}&isSGST=Y&isHMD=N&isALL=Y"
            resp = await client.get(list_url, timeout=10)
            ban_nos = _re.findall(r'banNo=(\d{8})', resp.text)
            if ban_nos:
                detail_resp = await client.get(
                    f"https://findbiz.nat.gov.tw/fts/query/QueryBrief/queryBrief.do?banNo={ban_nos[0]}",
                    timeout=10,
                )
                text = _re.sub(r'<[^>]+>', ' ', detail_resp.text)
                m = _TW_PHONE.search(text)
                if m:
                    return {"phone": _re.sub(r'[\s]+', '-', m.group(1).strip())}
            # 備援：list page 本身也試
            text = _re.sub(r'<[^>]+>', ' ', resp.text)
            m = _TW_PHONE.search(text)
            if m:
                return {"phone": _re.sub(r'[\s]+', '-', m.group(1).strip())}
    except Exception as e:
        logger.warning(f"find-phone findbiz error for {q!r}: {e}")

    # 0b-2. twincn.com 台灣公司網
    try:
        async with httpx.AsyncClient(headers=_SEARCH_HEADERS, follow_redirects=True, timeout=12) as client:
            twincn_url = f"https://www.twincn.com/search.aspx?r=1&q={_urlparse.quote(q)}"
            resp = await client.get(twincn_url, timeout=10)
            text = _re.sub(r'<[^>]+>', ' ', resp.text)
            m = _TW_PHONE.search(text)
            if m:
                return {"phone": _re.sub(r'[\s]+', '-', m.group(1).strip())}
    except Exception as e:
        logger.warning(f"find-phone twincn error for {q!r}: {e}")

    # 0b. 直接爬公司已知網站（最快最準）
    if website:
        try:
            urls_to_try = [website]
            for suffix in ['/contact', '/about', '/contactus', '/聯絡我們', '/聯絡']:
                base = website.rstrip('/')
                urls_to_try.append(base + suffix)
            async with httpx.AsyncClient(headers=_SEARCH_HEADERS, follow_redirects=True, timeout=10) as client:
                for url in urls_to_try:
                    try:
                        resp = await client.get(url, timeout=8)
                        # tel: 連結優先
                        for tel in _re.findall(r'href=["\']tel:([^"\']+)["\']', resp.text):
                            digits = _re.sub(r'\D', '', tel.lstrip('+'))
                            if digits.startswith('886'):
                                digits = '0' + digits[3:]
                            if 8 <= len(digits) <= 10 and digits.startswith('0'):
                                return {"phone": _fmt_phone_digits(digits)}
                        text = _re.sub(r'<[^>]+>', ' ', resp.text)
                        m = _TW_PHONE.search(text)
                        if m:
                            return {"phone": _re.sub(r'\s+', '-', m.group(1).strip())}
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"find-phone website scrape error for {website!r}: {e}")

    # 1. Gemini + Google Search Grounding（最準確，可抓 Knowledge Panel）
    gemini_key = _os2.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            prompt = (
                f"Search Google for the phone number of Taiwan company「{q}」. "
                f"Reply with ONLY the phone number digits and hyphens (e.g. 04-23125688 or 0912-345-678). "
                f"No explanation, no other text. If not found reply null."
            )
            try:
                tool = genai.protos.Tool(
                    google_search_retrieval=genai.protos.GoogleSearchRetrieval()
                )
                model = genai.GenerativeModel("gemini-2.0-flash", tools=[tool])
            except Exception:
                model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            logger.info(f"find-phone gemini raw for {q!r}: {raw!r}")
            if raw and raw.lower() != "null":
                # 先用 regex 直接 match
                m = _TW_PHONE.search(raw)
                if m:
                    return {"phone": _re.sub(r'\s+', '-', m.group(1).strip())}
                # 備援：把所有非數字去掉，只留數字，重新組成電話
                digits_only = _re.sub(r'\D', '', raw)
                if 8 <= len(digits_only) <= 10 and digits_only.startswith('0'):
                    return {"phone": _fmt_phone_digits(digits_only)}
        except Exception as e:
            logger.warning(f"find-phone gemini error for {q!r}: {e}")

    # 2. 台灣黃頁（yellow.com.tw）— 有結構化電話資料
    try:
        async with httpx.AsyncClient(headers=_SEARCH_HEADERS, follow_redirects=True, timeout=12) as client:
            yellow_url = f"https://www.yellow.com.tw/search/list?keyword={_urlparse.quote(q)}"
            resp = await client.get(yellow_url, timeout=10)
            text = _re.sub(r'<[^>]+>', ' ', resp.text)
            m = _TW_PHONE.search(text)
            if m:
                return {"phone": _re.sub(r'\s+', '-', m.group(1).strip())}
    except Exception as e:
        logger.warning(f"find-phone yellow.com.tw error for {q!r}: {e}")

    # 3. DuckDuckGo / Bing / Google 備援
    def _extract_phone_from_html(html: str) -> _Opt[str]:
        # 1. tel: 連結（Google Knowledge Panel 常用此格式）
        for tel in _re.findall(r'href=["\']tel:([^"\']+)["\']', html):
            digits = _re.sub(r'\D', '', tel.lstrip('+'))
            if digits.startswith('886'):
                digits = '0' + digits[3:]
            if 8 <= len(digits) <= 10 and digits.startswith('0'):
                return _fmt_phone_digits(digits)
        # 2. JSON-LD 結構化資料
        for script in _re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, _re.S):
            m = _TW_PHONE.search(script)
            if m:
                return _re.sub(r'\s+', '-', m.group(1).strip())
        # 3. 純文字
        text = _re.sub(r'<[^>]+>', ' ', html)
        m = _TW_PHONE.search(text)
        if m:
            return _re.sub(r'\s+', '-', m.group(1).strip())
        return None

    async def _search_for_phone(client, query: str) -> _Opt[str]:
        sources = [
            f"https://html.duckduckgo.com/html/?q={_urlparse.quote(query)}",
            f"https://www.bing.com/search?q={_urlparse.quote(query)}",
            f"https://www.google.com/search?q={_urlparse.quote(query)}&hl=zh-TW",
        ]
        for url in sources:
            try:
                resp = await client.get(url, timeout=12)
                result = _extract_phone_from_html(resp.text)
                if result:
                    return result
            except Exception:
                pass
        return None

    found = None
    try:
        async with httpx.AsyncClient(headers=_SEARCH_HEADERS, follow_redirects=True) as client:
            found = await _search_for_phone(client, f"{q} 電話")
            if not found:
                found = await _search_for_phone(client, f"{q} 聯絡電話 台灣")
    except Exception as e:
        logger.warning(f"find-phone fallback error for {q!r}: {e}")

    return {"phone": found}


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
            assigned_to=None,
            status=LeadStatus.claiming,
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
