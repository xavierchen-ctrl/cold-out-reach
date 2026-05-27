"""展覽名單爬蟲 - 委派給 custom_url 爬蟲處理各類展覽/公會廠商頁面"""
import logging
from typing import List

logger = logging.getLogger(__name__)

# 可用的展覽/公會廠商列表 URL（供使用者參考）
EXAMPLE_URLS = [
    "https://www.tibe.org.tw/tw/vendors/",                              # 台灣書展廠商
    "https://www.chanchao.com.tw/petsshow/taipei/visitorExhibitor.asp", # 台北寵物用品展
    "https://taiwanoutdoorshow-taichung.chanchao.com.tw/VisitorExhibitor", # 台中戶外用品展
]


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 100, **kwargs) -> List[dict]:
    """委派給 custom_url 爬蟲：支援 Chanchao、TIBE、燦坤等展覽網站格式"""
    # 若使用舊的預設 URL（已停用的域名），換成有效的示範 URL
    if not url or "exh.taitra.org.tw" in url:
        url = EXAMPLE_URLS[0]
        logger.info(f"exhibition: exh.taitra.org.tw 已停用，改用 {url}")

    try:
        from scrapers.custom_url import scrape as custom_scrape
        results = await custom_scrape(
            url=url,
            keyword=keyword,
            industry=industry or "展覽廠商",
            limit=limit,
            strict_name_filter=False,
        )
        return results
    except Exception as e:
        logger.error(f"exhibition scrape error: {e}")
        return []
