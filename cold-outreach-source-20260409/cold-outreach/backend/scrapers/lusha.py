"""
Lusha API 爬蟲
用公司名稱 + 聯絡人名字 enrich 電話 + Email + LinkedIn
API Docs: https://api.lusha.com
"""
import asyncio
import logging
import os
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

LUSHA_API_URL = "https://api.lusha.com/v2"

FALLBACK_DATA = [
    {
        "company_name": "91APP股份有限公司",
        "contact_name": "Andy Su",
        "title": "CEO",
        "email": "andy@91app.com",
        "phone": None,
        "website": "https://www.91app.com",
        "industry": "電商科技",
        "city": "台北",
        "company_size": "201-500人",
        "source": "lusha",
        "source_url": "https://www.lusha.com",
        "notes": "Lusha - 備用資料",
    },
]


async def enrich_person(
    client: httpx.AsyncClient,
    api_key: str,
    first_name: str,
    last_name: str,
    company: str,
    linkedin_url: Optional[str] = None,
) -> dict:
    """單筆聯絡人 enrich"""
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "company": {"name": company},
    }
    if linkedin_url:
        payload["linkedinUrl"] = linkedin_url

    try:
        resp = await client.get(
            f"{LUSHA_API_URL}/person",
            params={
                "firstName": first_name,
                "lastName": last_name,
                "company": company,
            },
            headers={"api_key": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("contact", {}).get("data", {})
    except Exception as e:
        logger.warning(f"Lusha enrich error ({first_name} {last_name} @ {company}): {e}")
    return {}


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 20, **kwargs) -> List[dict]:
    """
    Lusha 搜尋模式：
    - keyword 當作公司 domain 或公司名稱（e.g. "benq.com" 或 "BenQ"）
    - 用 Lusha Company API 拿公司電話 + 基本資訊
    - 再搜尋公司聯絡人（用 email 搜尋拿個人電話）
    limit: 最多搜幾筆
    """
    api_key = os.getenv("LUSHA_API_KEY", "")
    if not api_key:
        logger.warning("LUSHA_API_KEY not set, using fallback")
        return FALLBACK_DATA[:limit]

    lim = min(limit or 20, 100)

    # keyword 可以是：domain（如 benq.com）或公司名（如 BenQ）
    # 多個公司用逗號分隔
    keywords = [k.strip() for k in (keyword or "").split(",") if k.strip()]
    if not keywords:
        keywords = ["wavenet.com.tw"]  # 預設示範

    result = []
    async with httpx.AsyncClient(timeout=20) as client:
        for kw in keywords[:lim]:
            # 判斷是 domain 還是公司名
            is_domain = "." in kw and " " not in kw

            try:
                if is_domain:
                    params = {"domain": kw}
                else:
                    params = {"company": kw}

                resp = await client.get(
                    f"{LUSHA_API_URL}/company",
                    params=params,
                    headers={"api_key": api_key},
                    timeout=15,
                )
                await asyncio.sleep(0.5)  # rate limit: 5/min

                if resp.status_code == 429:
                    logger.warning("Lusha rate limit hit, sleeping 65s")
                    await asyncio.sleep(65)
                    resp = await client.get(f"{LUSHA_API_URL}/company", params=params, headers={"api_key": api_key})

                if resp.status_code != 200:
                    logger.warning(f"Lusha company error {resp.status_code} for {kw}")
                    continue

                data = resp.json().get("data", {})
                if not data:
                    continue

                company_name = data.get("name") or kw
                location = data.get("location", {})
                city = _normalize_city(location.get("city") or "")
                size_range = data.get("companySize", [])
                size_label = _size_label(size_range[0] if size_range else None)
                phones = data.get("phoneNumbers", [])
                phone = phones[0].get("internationalNumber") if phones else None
                homepage = data.get("homepageUrl") or (f"https://{kw}" if is_domain else None)
                ind = industry or data.get("mainIndustry") or "數位行銷"

                result.append({
                    "company_name": company_name,
                    "contact_name": None,
                    "title": None,
                    "email": None,
                    "phone": phone,
                    "website": homepage,
                    "industry": ind,
                    "city": city,
                    "company_size": size_label,
                    "source": "lusha",
                    "source_url": data.get("social", {}).get("linkedin") or "https://www.lusha.com",
                    "notes": f"員工數：{data.get('employeesOnLinkedin', '')} | Lusha Company ID: {data.get('lushaCompanyId', '')}",
                })

            except Exception as e:
                logger.error(f"Lusha company error ({kw}): {e}")
                continue

    logger.info(f"Lusha scrape done: {len(result)} companies")
    return result[:lim] if result else FALLBACK_DATA[:lim]


def _normalize_city(city_raw: str) -> str | None:
    if not city_raw:
        return None
    city_map = {
        "Taipei": "台北", "New Taipei": "新北", "Taichung": "台中",
        "Tainan": "台南", "Kaohsiung": "高雄", "Hsinchu": "新竹",
        "Taoyuan": "桃園", "Keelung": "基隆",
    }
    for eng, cht in city_map.items():
        if eng.lower() in city_raw.lower():
            return cht
    return city_raw


def _size_label(n) -> str | None:
    if not n:
        return None
    try:
        n = int(n)
        if n < 10: return "1-10人"
        if n < 50: return "11-50人"
        if n < 200: return "51-200人"
        if n < 500: return "201-500人"
        if n < 1000: return "501-1000人"
        return "1000人以上"
    except Exception:
        return None
