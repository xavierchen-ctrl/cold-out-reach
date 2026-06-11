"""
智能搜尋爬蟲 — 使用 OpenAI + DuckDuckGo 搜尋符合條件的公司
"""
import os
import json
import re
import logging
import httpx
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from openai import OpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_PROMPT = """請根據以下網路搜尋結果，找出最多 {lim} 個符合「{query}」條件的台灣公司或品牌。

搜尋結果摘要：
{snippets}

只回傳一個 JSON array（第一個字元必須是 [），不要加任何說明文字：
[
  {{
    "company_name": "公司或品牌名稱（必填）",
    "website": "官方網站連結（沒有填 null）",
    "industry": "行業別",
    "city": "城市（沒有填 null）",
    "notes": "50字內說明為何符合搜尋條件"
  }}
]"""

_PROMPT_NO_SNIPPETS = """請搜尋並列出最多 {lim} 個符合「{query}」條件的台灣公司或品牌。

只回傳一個 JSON array（第一個字元必須是 [），不要加任何說明文字：
[
  {{
    "company_name": "公司或品牌名稱（必填）",
    "website": "官方網站連結（沒有填 null）",
    "industry": "行業別",
    "city": "城市（沒有填 null）",
    "notes": "50字內說明為何符合搜尋條件"
  }}
]"""


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 20, **kwargs) -> List[dict]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 未設定，請在 Railway 環境變數中加入")

    parts = []
    if keyword:
        parts.append(keyword)
    if industry:
        parts.append(f"{industry}產業")
    if not parts:
        parts.append("台灣數位行銷品牌")

    query = " ".join(parts)
    lim = min(limit or 20, 50)

    # 1. DuckDuckGo 搜尋取得網頁摘要
    snippets = ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=12) as client:
            resp = await client.get(
                f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query + ' 台灣公司')}",
                timeout=10,
            )
            soup = BeautifulSoup(resp.text, "lxml")
            parts_snip = [
                r.get_text(" ", strip=True)
                for r in soup.select(".result__snippet, .result__body, .result__title")[:20]
                if r.get_text(strip=True)
            ]
            snippets = "\n".join(parts_snip)[:4000]
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")

    # 2. GPT 解析
    if snippets:
        prompt = _PROMPT.format(query=query, lim=lim, snippets=snippets)
    else:
        prompt = _PROMPT_NO_SNIPPETS.format(query=query, lim=lim)

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    text = (response.choices[0].message.content or "").strip()
    logger.info(f"OpenAI search '{query}': response length={len(text)}")

    # 3. 解析 JSON
    m = re.search(r'\[[\s\S]*\]', text)
    if not m:
        logger.warning(f"No JSON array in response: {text[:300]}")
        return []

    try:
        data = json.loads(m.group(0))
    except Exception:
        return []

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

    logger.info(f"Search '{query}': {len(results)} results")
    return results[:lim]
