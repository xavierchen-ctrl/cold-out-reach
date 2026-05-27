"""
Apollo.io API 爬蟲
搜尋台灣公司聯絡人名單
API Docs: https://docs.apollo.io/reference/people-api-search
"""
import asyncio
import logging
import os
from typing import List

import httpx

logger = logging.getLogger(__name__)

APOLLO_API_URL = "https://api.apollo.io/api/v1"

FALLBACK_DATA = [
    {
        "company_name": "91APP股份有限公司",
        "contact_name": "王志仁",
        "title": "CEO",
        "email": None,
        "phone": None,
        "website": "https://www.91app.com",
        "industry": "電商科技",
        "city": "台北",
        "company_size": "201-500人",
        "source": "apollo",
        "source_url": "https://app.apollo.io",
        "notes": "Apollo.io - 備用資料",
    },
]


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    """
    呼叫 Apollo.io API 搜尋台灣公司聯絡人。
    keyword: 職稱關鍵字（e.g. "Marketing Manager", "CEO"）
    industry: 產業篩選（e.g. "Marketing and Advertising", "Retail"）
    limit: 最多幾筆（最大 100/次，自動分頁）
    """
    api_key = os.getenv("APOLLO_API_KEY", "")
    if not api_key:
        logger.warning("APOLLO_API_KEY not set, using fallback")
        return FALLBACK_DATA[:limit]

    lim = min(limit or 100, 500)  # 最多 500 筆
    per_page = min(lim, 100)      # Apollo 每頁最多 100

    INDUSTRY_MAP = {
        "數位行銷": "Marketing and Advertising",
        "電商": "Internet",
        "零售": "Retail",
        "品牌": "Consumer Goods",
        "科技": "Information Technology and Services",
        "廣告": "Marketing and Advertising",
        "媒體": "Online Media",
    }

    # 預設職稱（針對數位行銷決策人）
    default_titles = [
        "Marketing Manager", "Marketing Director", "Digital Marketing Manager",
        "Brand Manager", "CEO", "CMO", "E-commerce Manager", "Head of Marketing",
        "Marketing Executive", "Business Development Manager",
    ]

    payload: dict = {
        "q_organization_locations": ["Taiwan"],
        "person_locations": ["Taiwan"],           # 人本人在台灣
        "person_country_codes": ["TW"],           # 嚴格限台灣
        "per_page": per_page,
        "page": 1,
        "reveal_personal_emails": True,
        "reveal_phone_number": True,
    }

    # 職稱：有傳 keyword 就用 keyword，否則用預設決策人職稱
    if keyword:
        payload["q_keywords"] = keyword
    else:
        payload["person_titles"] = default_titles

    if industry:
        eng_industry = INDUSTRY_MAP.get(industry, industry)
        # Apollo 用 q_organization_keyword_tags 傳產業文字（不是數字 ID）
        payload["q_organization_keyword_tags"] = [eng_industry]

    companies_map: dict = {}

    async with httpx.AsyncClient(timeout=30) as client:
        page = 1
        while len(companies_map) < lim:
            payload["page"] = page
            try:
                resp = await client.post(
                    f"{APOLLO_API_URL}/mixed_people/api_search",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Api-Key": api_key,
                    }
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Apollo API error (page {page}): {e}")
                break

            people = data.get("people", [])
            if not people:
                break

            # 批量 unlock email（bulk_match 一次最多 10 筆）
            enriched_map: dict = {}
            ids_to_enrich = [p["id"] for p in people if p.get("id") and p.get("has_email")]
            for i in range(0, len(ids_to_enrich), 10):
                batch = ids_to_enrich[i:i+10]
                try:
                    enrich_resp = await client.post(
                        f"{APOLLO_API_URL}/people/bulk_match",
                        json={"details": [{"id": pid} for pid in batch], "reveal_personal_emails": True},
                        headers={"Content-Type": "application/json", "X-Api-Key": api_key},
                    )
                    for enriched in (enrich_resp.json().get("matches") or []):
                        if enriched and enriched.get("id"):
                            enriched_map[enriched["id"]] = enriched
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Apollo bulk_match error: {e}")

            for person in people:
                # 過濾非台灣：country 必須是 TW 或 Taiwan 或 city 在台灣
                country = (person.get("country") or "").lower()
                city = (person.get("city") or "").lower()
                tw_cities = {"taipei", "new taipei", "taichung", "tainan", "kaohsiung",
                             "hsinchu", "taoyuan", "keelung", "zhongli", "banqiao"}
                is_taiwan = (
                    "taiwan" in country or country == "tw"
                    or any(c in city for c in tw_cities)
                )
                if not is_taiwan and country and "taiwan" not in country:
                    continue  # 跳過非台灣

                org = person.get("organization") or {}
                company_name = org.get("name", "").strip()
                if not company_name:
                    continue

                # 優先用 enriched 資料
                enriched = enriched_map.get(person.get("id", ""), {})
                first = person.get("first_name", "") or ""
                last = person.get("last_name", "") or ""
                contact_name = f"{first} {last}".strip() or None

                email = enriched.get("email") or person.get("email") or None
                # 取電話：direct_phone > sanitized_phone > phone_numbers[0]
                phone = (
                    enriched.get("direct_phone")
                    or person.get("direct_phone")
                    or person.get("sanitized_phone")
                    or (((person.get("phone_numbers") or [{}])[0]).get("sanitized_number"))
                    or None
                )

                city = _normalize_city(person.get("city") or org.get("city") or "")
                emp_count = org.get("estimated_num_employees") or org.get("num_suborganizations")
                size_label = _size_label(emp_count)

                # notes：記錄 email 狀態
                notes_parts = []
                if person.get("title"):
                    notes_parts.append(f"職稱：{person['title']}")
                if not email and person.get("has_email"):
                    notes_parts.append("⚠️ Email 需消耗 credits")

                if company_name not in companies_map:
                    companies_map[company_name] = {
                        "company_name": company_name,
                        "contact_name": contact_name,
                        "title": person.get("title") or None,
                        "email": email,
                        "phone": phone,
                        "website": org.get("website_url") or None,
                        "industry": industry or org.get("industry") or "數位行銷",
                        "city": city,
                        "company_size": size_label,
                        "source": "apollo",
                        "source_url": f"https://app.apollo.io/#/people/{person.get('id', '')}",
                        "notes": " | ".join(notes_parts) if notes_parts else None,
                    }
                if len(companies_map) >= lim:
                    break

            total = data.get("total_entries", 0)
            if page * per_page >= min(total, lim):
                break
            page += 1
            await asyncio.sleep(0.8)

    result = list(companies_map.values())
    logger.info(f"Apollo scrape done: {len(result)} companies (keyword={keyword}, industry={industry})")
    if not result:
        logger.warning("Apollo returned 0 results, using fallback")
        return FALLBACK_DATA[:lim]
    return result[:lim]


def _normalize_city(city_raw: str) -> str | None:
    if not city_raw:
        return None
    city_map = {
        "Taipei": "台北", "Taipei City": "台北",
        "New Taipei": "新北", "New Taipei City": "新北",
        "Taichung": "台中", "Taichung City": "台中",
        "Tainan": "台南", "Tainan City": "台南",
        "Kaohsiung": "高雄", "Kaohsiung City": "高雄",
        "Hsinchu": "新竹", "Taoyuan": "桃園",
    }
    for eng, cht in city_map.items():
        if eng.lower() in city_raw.lower():
            return cht
    return city_raw


def _size_label(emp_count) -> str | None:
    if not emp_count:
        return None
    try:
        n = int(emp_count)
        if n < 10: return "1-10人"
        if n < 50: return "11-50人"
        if n < 200: return "51-200人"
        if n < 500: return "201-500人"
        if n < 1000: return "501-1000人"
        return "1000人以上"
    except Exception:
        return None
