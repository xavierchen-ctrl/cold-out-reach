"""
Gemini 智能搜尋爬蟲
使用 Google Search Grounding 從網路即時搜尋符合條件的公司/品牌
"""
import os
import json
import re
import logging
from typing import List

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 20, **kwargs) -> List[dict]:
    """使用 Gemini + Google Search Grounding 搜尋符合條件的公司/品牌"""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 未設定")

    parts = []
    if keyword:
        parts.append(keyword)
    if industry:
        parts.append(f"{industry}產業")
    if not parts:
        parts.append("台灣數位行銷品牌")

    query = " ".join(parts)
    lim = min(limit or 20, 50)

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)

        prompt = f"""請使用 Google Search 搜尋：「{query}」

找出最多 {lim} 個符合條件的台灣公司、品牌或 YouTube 頻道。

只回傳一個 JSON array（第一個字元必須是 [），格式如下，不要加任何說明文字：
[
  {{
    "company_name": "公司或品牌名稱（必填）",
    "website": "官方網站或頻道連結（沒有填 null）",
    "industry": "行業別",
    "city": "城市（沒有填 null）",
    "notes": "50字內說明為何符合搜尋條件"
  }}
]"""

        try:
            tool = genai.protos.Tool(
                google_search_retrieval=genai.protos.GoogleSearchRetrieval()
            )
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                tools=[tool],
            )
        except Exception:
            # 若版本不支援 protos，降級為無 grounding
            logger.warning("Gemini: protos not available, falling back to no-grounding mode")
            model = genai.GenerativeModel(model_name="gemini-2.0-flash")

        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        logger.info(f"Gemini search '{query}': raw response length={len(text)}")

        # 提取 JSON array（允許 markdown code block 包住）
        m = re.search(r'\[[\s\S]*\]', text)
        if not m:
            logger.warning(f"Gemini search: no JSON array in response: {text[:300]}")
            return []

        data = json.loads(m.group(0))
        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = (item.get("company_name") or "").strip()
            if not name:
                continue
            results.append({
                "company_name": name,
                "contact_name": None,
                "email": None,
                "phone": None,
                "website": item.get("website") or None,
                "industry": item.get("industry") or industry,
                "city": item.get("city") or None,
                "company_size": None,
                "source": "gemini_search",
                "source_url": item.get("website") or None,
                "notes": item.get("notes") or None,
            })

        logger.info(f"Gemini search '{query}': {len(results)} results parsed")
        return results[:lim]

    except Exception as e:
        logger.error(f"Gemini search error: {e}")
        raise
