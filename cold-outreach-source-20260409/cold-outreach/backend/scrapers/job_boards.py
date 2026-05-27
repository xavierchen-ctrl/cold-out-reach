"""
B - 104 人力銀行 / 1111 人力銀行 爬蟲
搜尋「數位行銷」職缺的公司名單
"""
import asyncio
import io
import logging
import random
from typing import List, Optional

import httpx

# ── 1111 runes 字型解碼 ────────────────────────────────────────────────────────
# 1111 corp 頁面用私有 Unicode 字型混淆電話，每 2 個字元為一組，
# 第一個字元 → cmap → canonical glyph，第二個為 null (noise)。
_RUNES_CMAP: Optional[dict] = None   # 延遲載入
_RUNES_GLYPH_CHAR = {               # canonical glyph name → 顯示字元
    "uniE145": "(", "uniE0C5": ")", "uniE27D": "-",
    "uniE0C0": "0", "uniE0BC": "1", "uniE214": "2",
    "uniE0B5": "3", "uniE0D7": "4", "uniE129": "5",
    "uniE1C6": "6", "uniE0DA": "7", "uniE124": "8",
    "uniE0B1": "9",
}
_RUNES_FONT_URL = "https://www.1111.com.tw/_nuxt/0I5pJ268p0923e18.B1uDHa1B.woff2"


async def _get_runes_cmap() -> dict:
    global _RUNES_CMAP
    if _RUNES_CMAP is not None:
        return _RUNES_CMAP
    try:
        from fontTools.ttLib import TTFont
        async with httpx.AsyncClient(timeout=15, headers={"Referer": "https://www.1111.com.tw/"}) as c:
            r = await c.get(_RUNES_FONT_URL)
        font = TTFont(io.BytesIO(r.content))
        _RUNES_CMAP = font.getBestCmap()
    except Exception as e:
        logger.warning(f"runes font load failed: {e}")
        _RUNES_CMAP = {}
    return _RUNES_CMAP


def _decode_runes(text: str, cmap: dict) -> str:
    """PUA-encoded phone string → plain text (e.g. '(02)2570-8333')"""
    if not text or not cmap:
        return ""
    result = []
    for i in range(0, len(text), 2):
        cp = ord(text[i])
        gname = cmap.get(cp, "")
        result.append(_RUNES_GLYPH_CHAR.get(gname, ""))
    decoded = "".join(result).strip()
    return decoded if any(c.isdigit() for c in decoded) else ""

logger = logging.getLogger(__name__)

HEADERS_104 = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.104.com.tw/jobs/search/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

HEADERS_1111 = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.1111.com.tw/",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# 備用靜態資料
FALLBACK_DATA_104 = [
    {
        "company_name": "數位時代媒體股份有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": "https://www.bnext.com.tw",
        "industry": "數位媒體",
        "city": "台北",
        "company_size": "51-100人",
        "source": "104_job_board",
        "source_url": "https://www.104.com.tw",
        "notes": "職缺：數位行銷企劃",
    },
    {
        "company_name": "電商優化科技有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": None,
        "industry": "電商/科技",
        "city": "台北",
        "company_size": "11-50人",
        "source": "104_job_board",
        "source_url": "https://www.104.com.tw",
        "notes": "職缺：社群行銷專員",
    },
    {
        "company_name": "全球行銷顧問股份有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": "https://www.globalmarketing.com.tw",
        "industry": "行銷顧問",
        "city": "台北",
        "company_size": "101-500人",
        "source": "104_job_board",
        "source_url": "https://www.104.com.tw",
        "notes": "職缺：數位廣告經理",
    },
    {
        "company_name": "新媒體整合股份有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": None,
        "industry": "媒體整合",
        "city": "新北",
        "company_size": "51-100人",
        "source": "104_job_board",
        "source_url": "https://www.104.com.tw",
        "notes": "職缺：SEO行銷專員",
    },
    {
        "company_name": "創意互動傳播有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": "https://www.creative-interact.com.tw",
        "industry": "廣告/傳播",
        "city": "台北",
        "company_size": "11-50人",
        "source": "104_job_board",
        "source_url": "https://www.104.com.tw",
        "notes": "職缺：品牌行銷主任",
    },
]

FALLBACK_DATA_1111 = [
    {
        "company_name": "亞洲電商平台股份有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": None,
        "industry": "電商平台",
        "city": "台北",
        "company_size": "501-1000人",
        "source": "1111_job_board",
        "source_url": "https://www.1111.com.tw",
        "notes": "職缺：數位行銷總監",
    },
    {
        "company_name": "品牌策略整合顧問有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": None,
        "industry": "品牌顧問",
        "city": "台中",
        "company_size": "11-50人",
        "source": "1111_job_board",
        "source_url": "https://www.1111.com.tw",
        "notes": "職缺：社群媒體經理",
    },
    {
        "company_name": "雲端行銷科技股份有限公司",
        "contact_name": None,
        "email": None,
        "phone": None,
        "website": "https://www.cloudmartech.com.tw",
        "industry": "行銷科技",
        "city": "台北",
        "company_size": "51-100人",
        "source": "1111_job_board",
        "source_url": "https://www.1111.com.tw",
        "notes": "職缺：MarTech 行銷工程師",
    },
]

COMPANY_SIZE_MAP = {
    "1": "1-10人",
    "2": "11-50人",
    "3": "51-100人",
    "4": "101-500人",
    "5": "501-1000人",
    "6": "1001人以上",
}


def _extract_city(address: str) -> str | None:
    cities = ["台北", "新北", "桃園", "新竹", "台中", "台南", "高雄", "基隆", "宜蘭", "嘉義", "彰化", "南投", "雲林", "屏東", "苗栗", "台東", "花蓮"]
    for city in cities:
        if city in address:
            return city
    return None


def _deduplicate(items: List[dict]) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        key = item.get("company_name", "").strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


async def _scrape_104(url: str, keyword: str = "數位行銷", limit: int = 100) -> List[dict]:
    """104 人力銀行 JSON API（多頁抓取）"""
    import re as _re, urllib.parse

    api_url = "https://www.104.com.tw/jobs/search/api/jobs"

    # 從 url 解析 keyword（優先用傳入的 keyword 參數）
    if not keyword and "keyword=" in url:
        qs = urllib.parse.urlparse(url).query
        parsed = urllib.parse.parse_qs(qs)
        keyword = parsed.get("keyword", ["數位行銷"])[0]

    kw = keyword or "數位行銷"
    companies = []
    seen_names: set = set()
    page = 1
    per_page = 32   # 104 新 API 每頁約 30-32 筆

    async with httpx.AsyncClient(headers=HEADERS_104, timeout=30, follow_redirects=True) as client:
        while len(companies) < limit:
            params = {
                "keyword": kw,
                "order": "15",
                "asc": "0",
                "page": str(page),
                "mode": "s",
                "jobsource": "2018indexpoc",
            }
            await asyncio.sleep(random.uniform(0.8, 1.5))
            try:
                resp = await client.get(api_url, params=params)
                resp.raise_for_status()
                raw = resp.json()
            except Exception as e:
                logger.warning(f"104 page {page} error: {e}")
                break

            # 新 API：data 直接是陣列；舊 API：data.list
            data_val = raw.get("data", [])
            if isinstance(data_val, dict):
                jobs_list = data_val.get("list", [])
                total = data_val.get("totalCount", 0)
                last_page = (total + per_page - 1) // per_page
            else:
                jobs_list = data_val if isinstance(data_val, list) else []
                meta = raw.get("metadata", {})
                pagination = meta.get("pagination", {})
                total = pagination.get("total", 0)
                last_page = pagination.get("lastPage", 1)

            if not jobs_list:
                break

            for job in jobs_list:
                name = job.get("custName", "").strip()
                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                ind  = job.get("coIndustryDesc", "") or kw
                city = _extract_city(job.get("jobAddrNoDesc", "") or "")
                emp  = job.get("employeeCount") or job.get("coSize")
                size_label = (
                    f"{emp}人" if isinstance(emp, int) and emp > 0
                    else COMPANY_SIZE_MAP.get(str(emp), None)
                )
                job_title = job.get("jobName", "")

                # 公司網址：從 link.cust 取
                links = job.get("link", {})
                cust_page = links.get("cust", "") or ""
                website = job.get("custUrl") or None

                # 從職缺描述抓電話 / email
                desc = job.get("description") or job.get("descSnippet") or ""
                phone_m = _re.search(
                    r'(?:電話|手機|聯絡)[：:\s]*'
                    r'((?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4})',
                    desc
                )
                email_m = _re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', desc)
                phone = phone_m.group(1).strip() if phone_m else None
                email = email_m.group(0) if email_m else None

                companies.append({
                    "company_name": name,
                    "contact_name": None,
                    "email": email,
                    "phone": phone,
                    "website": website,
                    "industry": ind,
                    "city": city,
                    "company_size": size_label,
                    "source": "104_job_board",
                    "source_url": cust_page or f"https://www.104.com.tw/company/ajax/content/{job.get('custNo','')}",
                    "notes": f"職缺：{job_title}" if job_title else None,
                })
                if len(companies) >= limit:
                    break

            if page >= last_page:
                break
            page += 1

    return companies


async def _scrape_1111(url: str, keyword: str = "數位行銷", limit: int = 100) -> List[dict]:
    """1111 人力銀行 Playwright（多頁 + Altcha 自動解題）"""
    import urllib.parse
    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup as _BS

    # 優先用傳入 keyword，再從 url 的 ks= 解析，最後預設
    if not keyword and "ks=" in url:
        parsed_url = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed_url.query)
        keyword = qs.get("ks", ["數位行銷"])[0]
    kw = keyword or "數位行銷"

    # 建立基底搜尋 URL（從 page=1 開始翻頁）
    base_search = f"https://www.1111.com.tw/search/job?col=ab&sort=desc&ks={urllib.parse.quote(kw)}"

    companies: List[dict] = []
    seen_names: set = set()
    page_no = 1
    max_pages = max(1, (limit + 9) // 10)  # 每頁 10 筆

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        while len(companies) < limit and page_no <= max_pages:
            page_url = f"{base_search}&page={page_no}"
            try:
                # 第一次載入（Altcha challenge 頁）
                await page.goto(page_url, timeout=30000, wait_until="load")
                # Altcha auto=onload 約 1~3 秒 CPU proof-of-work 後觸發 window.location.reload()
                # 等 4 秒確保 reload 已完成觸發
                await page.wait_for_timeout(4000)
                # 等 reload 後的真實頁面完全穩定
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass  # networkidle 若超時就繼續
                await page.wait_for_timeout(500)
            except Exception as e:
                logger.warning(f"1111 page {page_no} nav error: {e}")
                break

            content = await page.content()
            soup = _BS(content, "lxml")
            cards = soup.select("div.job-card")

            if not cards:
                break  # 沒有更多資料

            # 收集本頁所有公司的基本資料 + corp_url
            page_items = []
            for card in cards:
                import re as _re
                name_el    = card.select_one("h2.inline")
                ind_el     = card.select_one("h3.inline")
                city_el    = card.select_one("a.job-card-condition__text")
                title_el   = card.select_one("h2.whitespace-wrap, h2[class*='whitespace']")
                corp_link  = card.select_one("a[href*='/corp/']")
                desc_text  = card.get_text(" ", strip=True)

                name = name_el.get_text(strip=True) if name_el else ""
                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                industry  = ind_el.get_text(strip=True) if ind_el else (kw)
                city_raw  = city_el.get_text(strip=True) if city_el else ""
                city      = _extract_city(city_raw)
                job_title = title_el.get_text(strip=True) if title_el else ""
                job_title = _re.sub(r'^\[.+?\]', '', job_title).strip()

                # 從職缺描述抓電話（有些公司直接在描述裡寫聯絡方式）
                phone_m = _re.search(
                    r'(?:手機|電話|聯絡)[：:\s]*([0-9]{2,4}[-\s]?[0-9]{3,4}[-\s]?[0-9]{3,4})',
                    desc_text
                )
                phone = phone_m.group(1).strip() if phone_m else None

                # 從職缺描述抓 email
                email_m = _re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', desc_text)
                email = email_m.group(0) if email_m else None

                corp_href = corp_link.get("href", "") if corp_link else ""
                corp_url = f"https://www.1111.com.tw{corp_href}" if corp_href.startswith("/") else corp_href

                page_items.append({
                    "company_name": name,
                    "industry": industry,
                    "city": city,
                    "job_title": job_title,
                    "phone": phone,
                    "email": email,
                    "corp_url": corp_url,
                })

            # 第二層：逐一訪問 corp 頁面抓公司網址 + 電話（runes 解碼）
            runes_cmap = await _get_runes_cmap()
            detail_page = await ctx.new_page()
            for item in page_items:
                if len(companies) >= limit:
                    break
                website = None
                corp_phone = item["phone"]  # 已從職缺描述抓到的電話
                if item["corp_url"]:
                    try:
                        await detail_page.goto(item["corp_url"], timeout=20000, wait_until="load")
                        await detail_page.wait_for_timeout(3000)

                        # 公司電話：用 Playwright locator 取 runes span 的 PUA 文字再解碼
                        if not corp_phone:
                            try:
                                runes_el = detail_page.locator("li:has(h3:text-is('公司電話')) span.runes")
                                if await runes_el.count() > 0:
                                    runes_text = await runes_el.first.inner_text(timeout=2000)
                                    decoded = _decode_runes(runes_text, runes_cmap)
                                    if decoded:
                                        corp_phone = decoded
                            except Exception:
                                pass

                        dcontent = await detail_page.content()
                        dsoup = _BS(dcontent, "lxml")

                        # 公司網址：在 <h3>公司網址</h3> 後的 <a>
                        for h3 in dsoup.find_all("h3"):
                            if "公司網址" in h3.get_text():
                                a_el = h3.find_next("a")
                                if a_el and a_el.get("href", "").startswith("http"):
                                    website = a_el["href"]
                                    break

                        # 從公司頁嘗試抓 email
                        if not item["email"]:
                            import re as _re2
                            full_text = dsoup.get_text(" ", strip=True)
                            em = _re2.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', full_text)
                            if em and "1111" not in em.group(0):
                                item["email"] = em.group(0)

                    except Exception as e:
                        logger.debug(f"1111 corp detail error for {item['company_name']}: {e}")

                companies.append({
                    "company_name": item["company_name"],
                    "contact_name": None,
                    "email": item["email"],
                    "phone": corp_phone,
                    "website": website,
                    "industry": item["industry"],
                    "city": item["city"],
                    "company_size": None,
                    "source": "1111_job_board",
                    "source_url": item["corp_url"] or page_url,
                    "notes": f"職缺：{item['job_title']}" if item["job_title"] else None,
                })
            await detail_page.close()

            page_no += 1
            await asyncio.sleep(random.uniform(0.5, 1.0))

        await browser.close()

    return companies


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    """
    爬取 104 或 1111 人力銀行職缺公司名單。
    keyword: 搜尋關鍵字（預設 "數位行銷"）
    industry: 自訂產業標籤（覆蓋爬取到的產業）
    limit: 最多抓幾筆（預設 100）
    """
    is_1111 = "1111.com.tw" in url
    kw = keyword or "數位行銷"
    lim = limit or 100

    try:
        if is_1111:
            companies = await _scrape_1111(url, keyword=kw, limit=lim)
            if not companies:
                logger.warning("1111: no companies parsed, using fallback")
                return FALLBACK_DATA_1111[:lim]
        else:
            companies = await _scrape_104(url, keyword=kw, limit=lim)
            if not companies:
                logger.warning("104: no companies parsed, using fallback")
                return FALLBACK_DATA_104[:lim]

        # 若有自訂 industry，覆蓋所有結果
        if industry:
            for c in companies:
                c["industry"] = industry

        return _deduplicate(companies)

    except Exception as e:
        logger.error(f"job_boards scraper error ({url}): {e}")
        fallback = FALLBACK_DATA_1111 if is_1111 else FALLBACK_DATA_104
        return fallback[:lim]
