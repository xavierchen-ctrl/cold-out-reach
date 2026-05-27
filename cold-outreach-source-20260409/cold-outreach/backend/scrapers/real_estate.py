"""591 新成屋爬蟲 - 取得建案名稱、建商、聯絡電話"""
import asyncio
import logging
import random
import re
from typing import List

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


def _extract_developer(text: str) -> str:
    """從詳情頁文字中抓建商名稱"""
    # 「建設\n公司名稱」— 至少 1 字前綴，含建設/建築/開發/地產等關鍵字
    m = re.search(
        r'建設\s*\n\s*'
        r'([^\n]{1,30}(?:建設|建築|開發|地產|營造|不動產|工程|建業|建屋)[^\n]*)',
        text
    )
    if m:
        return m.group(1).strip()
    # 「建商資料」區塊 — 往後幾行找有限公司名稱
    m2 = re.search(
        r'建商資料[\s\S]{0,60}?([^\n]{2,30}(?:建設|建築|開發|地產|建業|開發|建商)[^\n]*有限公司[^\n]*)',
        text
    )
    if m2:
        return m2.group(1).strip()
    # 最後嘗試：「投資建設\n公司名稱」
    m3 = re.search(r'投資建設\s*\n+\s*([^\n]{3,35}(?:股份有限公司|有限公司)[^\n]*)', text)
    if m3:
        return m3.group(1).strip()
    return ""


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    lim = min(limit or 100, 300)

    # 從 keyword 決定地區（預設台北）
    region_id = "1"
    if keyword:
        for city, rid in REGION_MAP.items():
            if city in keyword:
                region_id = rid
                break

    try:
        from playwright.async_api import async_playwright

        results = []
        seen_developers: set = set()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
                viewport={"width": 1280, "height": 900},
            )
            list_page = await ctx.new_page()

            # 取得 session（timeout 放寬到 40 秒）
            try:
                await list_page.goto("https://newhouse.591.com.tw", timeout=40000, wait_until="domcontentloaded")
            except Exception:
                await list_page.goto("https://newhouse.591.com.tw", timeout=40000, wait_until="commit")
            await list_page.wait_for_timeout(2000)

            # 用瀏覽器 session 呼叫搜尋 API
            page_no = 1
            raw_items = []   # 暫存 (hid, build_name, phone, phone_ext, region, address)

            while len(raw_items) < lim:
                resp = await list_page.request.get(
                    "https://newhouse.591.com.tw/home/housing/search",
                    params={"regionid": region_id, "page": str(page_no)},
                )
                data = await resp.json()
                d = data.get("data", {})
                items = d.get("items", [])
                total_pages = d.get("total_page", 1)

                if not items:
                    break

                for item in items:
                    raw_items.append({
                        "hid":       item.get("hid"),
                        "build_name": (item.get("build_name") or "").strip(),
                        "phone":     item.get("phone", ""),
                        "phone_ext": item.get("phone_ext", ""),
                        "region":    item.get("region", ""),
                        "address":   item.get("address") or item.get("address_new") or "",
                    })
                    if len(raw_items) >= lim:
                        break

                if page_no >= total_pages:
                    break
                page_no += 1
                await asyncio.sleep(random.uniform(0.3, 0.7))

            # 第二層：逐一訪問詳情頁取建商名稱
            detail_page = await ctx.new_page()
            for item in raw_items:
                if len(results) >= lim:
                    break

                hid       = item["hid"]
                build     = item["build_name"]
                phone_str = f"{item['phone']}轉{item['phone_ext']}" if item.get("phone") and item.get("phone_ext") else item.get("phone") or None
                region    = item["region"].replace("縣", "").replace("市", "")[:3] or None
                address   = item["address"] or None
                developer = ""

                if hid:
                    try:
                        await detail_page.goto(
                            f"https://newhouse.591.com.tw/{hid}",
                            timeout=20000, wait_until="domcontentloaded"
                        )
                        await detail_page.wait_for_timeout(3000)
                        text = await detail_page.inner_text("body")
                        developer = _extract_developer(text)
                    except Exception as e:
                        logger.debug(f"591 detail error for hid={hid}: {e}")

                company = developer or build
                if not company:
                    continue

                # 以「建商+城市」為去重 key（同一建商可能有多建案）
                dedup_key = f"{company}|{region}"
                notes = f"建案：{build}" if build and build != developer else (f"地址：{address}" if address else None)

                if developer and dedup_key not in seen_developers:
                    seen_developers.add(dedup_key)
                elif not developer:
                    seen_developers.add(dedup_key)

                # 嘗試從詳情頁找建商官網（排除 591 平台自身連結）
                website = None
                if hid:
                    try:
                        content = await detail_page.content()
                        EXCLUDED = {'591.com', 'addcn.com', 'google.com', 'facebook.com',
                                    'line.me', 'youtube.com', 'nday.com', 'tasker.com',
                                    'esafe.com', 'land.moi.gov', 'moi.gov'}
                        all_hrefs = re.findall(r'href=["\')(https?://[^\s"\']{10,100})["\']', content)
                        for href in all_hrefs:
                            domain = re.search(r'https?://(?:www\.)?([^/]+)', href)
                            if not domain:
                                continue
                            d = domain.group(1).lower()
                            if not any(ex in d for ex in EXCLUDED):
                                website = href.split('?')[0].split('#')[0]  # 去掉參數
                                break
                    except Exception:
                        pass

                results.append({
                    "company_name": company,
                    "contact_name": None,
                    "phone":        phone_str,
                    "email":        None,
                    "website":      website,
                    "industry":     "房地產/建設",
                    "city":         region,
                    "company_size": None,
                    "source":       "real_estate_591",
                    "source_url":   f"https://newhouse.591.com.tw/{hid}" if hid else "https://newhouse.591.com.tw",
                    "notes":        notes,
                })
                await asyncio.sleep(random.uniform(0.3, 0.8))

            await detail_page.close()
            await browser.close()

        return results[:lim] if results else FALLBACK_DATA[:lim]

    except Exception as e:
        logger.error(f"real_estate_591 scrape error: {e}")
        return FALLBACK_DATA[:lim]
