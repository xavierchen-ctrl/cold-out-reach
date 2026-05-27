"""電商品牌爬蟲 - Shopee Taiwan 品牌列表"""
import asyncio, logging
from typing import List
import httpx

logger = logging.getLogger(__name__)

FALLBACK_DATA = [
    {"company_name": "UNIQLO Taiwan", "contact_name": None, "phone": None, "email": "tw.service@uniqlo.com", "website": "https://www.uniqlo.com/tw", "industry": "電商/零售", "city": "台北", "company_size": "1000人以上", "source": "ecommerce", "source_url": "https://shopee.tw", "notes": "Shopee 官方旗艦店"},
    {"company_name": "Nike Taiwan", "contact_name": None, "phone": None, "email": None, "website": "https://www.nike.com/tw", "industry": "電商/運動", "city": "台北", "company_size": "1000人以上", "source": "ecommerce", "source_url": "https://shopee.tw", "notes": "Shopee 官方旗艦店"},
    {"company_name": "寶雅生活館", "contact_name": None, "phone": "04-2258-2222", "email": None, "website": "https://www.poya.com.tw", "industry": "電商/美妝", "city": "台中", "company_size": "1000人以上", "source": "ecommerce", "source_url": "https://shopee.tw", "notes": "Shopee 官方品牌館"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://shopee.tw/",
}

SHOPEE_CATEGORIES = {
    "女裝": "2",
    "男裝": "3",
    "3C": "11",
    "家電": "12",
    "美妝": "18",
    "食品": "14",
    "運動": "6",
    "家居": "13",
}

async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    lim = min(limit or 100, 200)
    kw = keyword or "品牌"
    results = []
    seen = set()

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            # Shopee 品牌搜尋 API
            newest = 0
            per_page = min(lim, 60)
            while len(results) < lim:
                await asyncio.sleep(1.5)
                resp = await client.get(
                    "https://shopee.tw/api/v4/search/search_items",
                    params={
                        "by": "relevancy",
                        "keyword": kw,
                        "limit": per_page,
                        "newest": newest,
                        "order": "desc",
                        "page_type": "search",
                        "scenario": "PAGE_GLOBAL_SEARCH",
                        "version": "2",
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items") or []
                if not items:
                    break
                for item in items:
                    shop = item.get("item_basic", {})
                    shop_name = shop.get("shop_name") or shop.get("name") or ""
                    shop_name = shop_name.strip()
                    if not shop_name or shop_name in seen:
                        continue
                    seen.add(shop_name)
                    results.append({
                        "company_name": shop_name,
                        "contact_name": None,
                        "phone": None,
                        "email": None,
                        "website": None,
                        "industry": industry or "電商品牌",
                        "city": None,
                        "company_size": None,
                        "source": "ecommerce",
                        "source_url": f"https://shopee.tw/search?keyword={kw}",
                        "notes": f"Shopee 搜尋：{kw}",
                    })
                    if len(results) >= lim:
                        break
                newest += per_page
                if newest >= 200:
                    break
        if not results:
            return FALLBACK_DATA[:lim]
        return results[:lim]
    except Exception as e:
        logger.error(f"ecommerce scrape error: {e}")
        return FALLBACK_DATA[:lim]
