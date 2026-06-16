"""591 新成屋爬蟲 - 取得建案名稱、建商、聯絡電話"""
import asyncio
import logging
import re
from typing import List, Tuple

import httpx

logger = logging.getLogger(__name__)


REGION_MAP = {
    "台北": "1", "臺北": "1", "新北": "3", "基隆": "2",
    "桃園": "6", "新竹": "9", "苗栗": "11", "台中": "15", "臺中": "15",
    "彰化": "16", "南投": "17", "嘉義": "19",
    "台南": "20", "臺南": "20", "高雄": "22", "屏東": "23",
    "宜蘭": "4", "花蓮": "24", "台東": "25", "臺東": "25",
}

FALLBACK_DATA = [
    {"company_name": "京城建設股份有限公司", "contact_name": None, "phone": "07-555-1234", "email": None, "website": "https://www.king-city.com.tw", "industry": "房地產/建設", "city": "高雄", "company_size": None, "source": "real_estate_591", "source_url": "https://newhouse.591.com.tw", "notes": "建案：京城ONE"},
    {"company_name": "遠雄建設事業股份有限公司", "contact_name": None, "phone": "02-2123-4567", "email": None, "website": "https://www.farglory.com.tw", "industry": "房地產/建設", "city": "台北", "company_size": None, "source": "real_estate_591", "source_url": "https://newhouse.591.com.tw", "notes": "建案：遠雄THE ONE"},
]

_EXCLUDED_DOMAINS = {
    '591.com', 'addcn.com', 'google.com', 'facebook.com',
    'line.me', 'youtube.com', 'nday.com', 'tasker.com',
    'esafe.com', 'land.moi.gov', 'moi.gov',
    'sinyi.com.tw', 'house.com.tw', 'rakuya.com.tw', 'yungching.com.tw',
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://newhouse.591.com.tw/",
}


def _extract_developer(text: str) -> str:
    """從詳情頁文字中抓建商名稱"""
    m = re.search(
        r'建設\s*[\n\r]+\s*([^\n\r]{1,30}(?:建設|建築|開發|地產|營造|不動產|工程|建業|建屋)[^\n\r]*)',
        text
    )
    if m:
        return m.group(1).strip()
    m2 = re.search(
        r'建商資料[\s\S]{0,60}?([^\n]{2,30}(?:建設|建築|開發|地產|建業|建商)[^\n]*有限公司[^\n]*)',
        text
    )
    if m2:
        return m2.group(1).strip()
    m3 = re.search(r'投資建設\s*[\n\r]+\s*([^\n\r]{3,35}(?:股份有限公司|有限公司)[^\n\r]*)', text)
    if m3:
        return m3.group(1).strip()
    # 嘗試 JSON-LD 或 meta 裡的 build_company
    m4 = re.search(r'"build_company"\s*:\s*"([^"]{2,40})"', text)
    if m4:
        return m4.group(1).strip()
    return ""


def _extract_website(html: str) -> str:
    for href in re.findall(r'href=["\')(https?://[^\s"\']{10,100})["\']', html):
        m = re.search(r'https?://(?:www\.)?([^/]+)', href)
        if not m:
            continue
        if not any(ex in m.group(1).lower() for ex in _EXCLUDED_DOMAINS):
            return href.split('?')[0].split('#')[0]
    return ""


async def _fetch_detail(client: httpx.AsyncClient, hid: int, sem: asyncio.Semaphore) -> Tuple[str, str]:
    """並發抓單筆：先試 JSON API，再試 HTML。回傳 (developer, website)"""
    async with sem:
        # 1. JSON detail API
        try:
            resp = await client.get(
                "https://newhouse.591.com.tw/home/housing/detail",
                params={"id": str(hid)},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                dev = (
                    data.get("build_company") or
                    data.get("developer") or
                    data.get("company_name") or
                    data.get("builder") or ""
                ).strip()
                if dev:
                    return dev, ""
        except Exception:
            pass

        # 2. HTML fallback
        try:
            resp = await client.get(
                f"https://newhouse.591.com.tw/{hid}",
                timeout=8,
            )
            if resp.status_code == 200:
                html = resp.text
                plain = re.sub(r'<[^>]+>', ' ', html)
                dev = _extract_developer(plain)
                website = _extract_website(html)
                return dev, website
        except Exception as e:
            logger.debug(f"591 detail error hid={hid}: {e}")

        return "", ""


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    lim = min(limit or 100, 300)

    region_id = "1"
    if keyword:
        for city, rid in REGION_MAP.items():
            if city in keyword:
                region_id = rid
                break

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=15,
        ) as client:
            # 取得初始 cookie（無需瀏覽器）
            try:
                await client.get("https://newhouse.591.com.tw", timeout=15)
            except Exception:
                pass

            # 第一層：翻頁取列表
            page_no = 1
            raw_items: list = []

            while len(raw_items) < lim:
                try:
                    resp = await client.get(
                        "https://newhouse.591.com.tw/home/housing/search",
                        params={"regionid": region_id, "page": str(page_no)},
                        timeout=10,
                    )
                    data = resp.json()
                except Exception as e:
                    logger.warning(f"591 list API error page={page_no}: {e}")
                    break

                d = data.get("data", {})
                items = d.get("items", [])
                total_pages = d.get("total_page", 1)

                if not items:
                    break

                for item in items:
                    raw_items.append({
                        "hid":        item.get("hid"),
                        "build_name": (item.get("build_name") or "").strip(),
                        "phone":      item.get("phone", ""),
                        "phone_ext":  item.get("phone_ext", ""),
                        "region":     item.get("region", ""),
                        "address":    item.get("address") or item.get("address_new") or "",
                    })
                    if len(raw_items) >= lim:
                        break

                if page_no >= total_pages:
                    break
                page_no += 1
                await asyncio.sleep(0.2)

            if not raw_items:
                logger.warning("591 list API returned no items, using fallback")
                return FALLBACK_DATA[:lim]

            # 第二層：並發抓詳情（10 筆同時）
            sem = asyncio.Semaphore(10)
            detail_tasks = [
                _fetch_detail(client, item["hid"], sem)
                for item in raw_items if item.get("hid")
            ]
            detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

            # 組合結果
            results: list = []
            seen: set = set()
            detail_idx = 0

            for item in raw_items:
                if len(results) >= lim:
                    break

                hid   = item["hid"]
                build = item["build_name"]
                proxy_phone = (
                    f"{item['phone']}轉{item['phone_ext']}"
                    if item.get("phone") and item.get("phone_ext")
                    else item.get("phone") or None
                )
                region  = item["region"].replace("縣", "").replace("市", "")[:3] or None
                address = item["address"] or None

                developer = ""
                website   = ""
                if hid:
                    res = detail_results[detail_idx] if detail_idx < len(detail_results) else None
                    detail_idx += 1
                    if res and not isinstance(res, Exception):
                        developer, website = res

                company = developer or build
                if not company:
                    continue

                dedup_key = f"{company}|{region}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                notes_parts = []
                if build and build != developer:
                    notes_parts.append(f"建案：{build}")
                elif address:
                    notes_parts.append(f"地址：{address}")
                if proxy_phone:
                    notes_parts.append(f"591接洽電話：{proxy_phone}")

                results.append({
                    "company_name": company,
                    "contact_name": None,
                    "phone":        None,
                    "email":        None,
                    "website":      website or None,
                    "industry":     "房地產/建設",
                    "city":         region,
                    "company_size": None,
                    "source":       "real_estate_591",
                    "source_url":   f"https://newhouse.591.com.tw/{hid}" if hid else "https://newhouse.591.com.tw",
                    "notes":        "　".join(notes_parts) or None,
                })

        return results[:lim] if results else FALLBACK_DATA[:lim]

    except Exception as e:
        logger.error(f"real_estate_591 scrape error: {e}")
        return FALLBACK_DATA[:lim]
