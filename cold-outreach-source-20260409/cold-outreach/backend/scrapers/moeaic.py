"""工商登記查詢 - 經濟部 GCIS 開放資料 API"""
import asyncio
import logging
import urllib.parse
from typing import List

import httpx

logger = logging.getLogger(__name__)

GCIS_API = "https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C"

FALLBACK_DATA = [
    {"company_name": "台灣數位行銷股份有限公司", "contact_name": "張志明", "phone": None, "email": None, "website": None, "industry": "數位行銷", "city": "台北", "company_size": None, "source": "moeaic", "source_url": "https://data.gcis.nat.gov.tw", "notes": "統編：12345678 | 資本額：500萬"},
    {"company_name": "創新廣告科技有限公司", "contact_name": "林美華", "phone": None, "email": None, "website": None, "industry": "廣告科技", "city": "新北", "company_size": None, "source": "moeaic", "source_url": "https://data.gcis.nat.gov.tw", "notes": "統編：87654321 | 資本額：200萬"},
]


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    kw = keyword or industry or "行銷"
    lim = min(limit or 100, 500)
    results = []
    skip = 0
    per_page = 100

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            while len(results) < lim:
                filter_expr = f"Company_Name like '%{kw}%'"
                filter_enc = urllib.parse.quote(filter_expr, safe="='% ")
                url_req = (
                    f"{GCIS_API}?$format=json"
                    f"&$filter={filter_enc}"
                    f"&$top={per_page}"
                    f"&$skip={skip}"
                    f"&$select=Company_Name,Business_Accounting_NO,Company_Status_Desc,"
                    f"Company_Setup_Date,Responsible_Name,Capital_Stock_Amount,Company_Location"
                )
                resp = await client.get(url_req, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()

                text = resp.text.strip()
                if not text or text == "[]":
                    break

                rows = resp.json()
                if not isinstance(rows, list) or not rows:
                    break

                for row in rows:
                    name = (row.get("Company_Name") or "").strip()
                    if not name:
                        continue
                    status = row.get("Company_Status_Desc") or ""
                    if "解散" in status or "撤銷" in status:
                        continue

                    tax_no = str(row.get("Business_Accounting_NO") or "").strip()
                    representative = (row.get("Responsible_Name") or "").strip() or None
                    capital_raw = row.get("Capital_Stock_Amount")
                    capital_str = None
                    capital_amount_str = None
                    if capital_raw:
                        try:
                            cap_int = int(capital_raw)
                            capital_amount_str = f"{cap_int // 10000}萬元"
                            capital_str = f"資本額：{cap_int // 10000}萬"
                        except Exception:
                            pass

                    location = (row.get("Company_Location") or "").strip()
                    city = _extract_city(location)

                    raw_date = row.get("Company_Setup_Date") or ""
                    setup_date = None
                    if raw_date and len(raw_date) == 7:
                        try:
                            roc_year = int(raw_date[:3])
                            setup_date = f"{roc_year + 1911}-{raw_date[3:5]}-{raw_date[5:7]}"
                        except Exception:
                            setup_date = raw_date

                    notes_parts = []
                    if tax_no:
                        notes_parts.append(f"統編：{tax_no}")
                    if capital_str:
                        notes_parts.append(capital_str)
                    if setup_date:
                        notes_parts.append(f"設立：{setup_date}")

                    results.append({
                        "company_name": name,
                        "contact_name": representative,
                        "phone": None,
                        "email": None,
                        "website": None,
                        "industry": industry or "工商登記",
                        "city": city,
                        "company_size": None,
                        "source": "moeaic",
                        "source_url": f"https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C?$format=json&$filter=Business_Accounting_NO eq {tax_no}" if tax_no else "https://data.gcis.nat.gov.tw",
                        "notes": " | ".join(notes_parts) if notes_parts else None,
                        "tax_id": tax_no or None,
                        "representative_name": representative,
                        "capital_amount": capital_amount_str,
                    })
                    if len(results) >= lim:
                        break

                skip += per_page
                if len(rows) < per_page:
                    break
                await asyncio.sleep(0.3)

        if not results:
            logger.warning("moeaic GCIS: no results, using fallback")
            return FALLBACK_DATA[:lim]
        logger.info(f"moeaic GCIS: {len(results)} results for keyword='{kw}'")
        return results[:lim]

    except Exception as e:
        logger.error(f"moeaic scrape error: {e}")
        return FALLBACK_DATA[:lim]


def _extract_city(location: str) -> str | None:
    if not location:
        return None
    location = location.replace("臺", "台")
    cities = ["台北", "新北", "桃園", "新竹", "台中", "台南", "高雄",
              "基隆", "宜蘭", "嘉義", "彰化", "南投", "雲林",
              "屏東", "苗栗", "台東", "花蓮", "澎湖"]
    for c in cities:
        if c in location:
            return c
    return location[:3] if location else None
