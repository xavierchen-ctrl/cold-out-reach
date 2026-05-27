"""
signals.py — 含金量分析 router
POST /api/leads/{lead_id}/signals/analyze
"""
import re
import httpx
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Lead, User
from auth import get_current_user

router = APIRouter(prefix="/api/leads", tags=["signals"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


class AnalyzeRequest(BaseModel):
    website_url: Optional[str] = None


class SignalsResponse(BaseModel):
    tech_signals: dict
    ad_signals: dict
    social_signals: dict
    operations_signals: dict   # 積極營運指標
    market_signals: dict       # 市場體量指標
    wallet_signals: dict       # 口袋深度指標
    enriched_score: int
    score_breakdown: dict      # 分項得分說明
    inferred_website: Optional[str] = None


def extract_domain(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    match = re.search(r"https?://([^/]+)", url)
    return match.group(1) if match else url


async def fetch_website_html(url: str) -> Optional[str]:
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:
            res = await client.get(url)
            return res.text[:50000]
    except Exception as e:
        print(f"[signals] fetch website error: {e}")
        return None


async def fetch_website_scripts(url: str, html: str) -> str:
    """抓取官網引用的 JS 檔案內容，找廣告追蹤碼"""
    if not html:
        return ""

    # 從 HTML 找所有 <script src="...">
    script_urls = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)

    # 只抓可能含追蹤碼的 script（GTM、analytics、ads 相關）
    tracking_patterns = ['gtm', 'analytics', 'fbevents', 'pixel', 'ads', 'tag', 'tracking', 'gtag', '_next/static']
    relevant_scripts = []
    for src in script_urls[:20]:  # 最多檢查 20 個
        src_lower = src.lower()
        if any(p in src_lower for p in tracking_patterns):
            relevant_scripts.append(src)

    # 補全相對路徑
    base_url = re.match(r'(https?://[^/]+)', url)
    base = base_url.group(1) if base_url else ""

    combined = ""
    async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
        for src in relevant_scripts[:5]:  # 最多抓 5 個
            try:
                full_url = src if src.startswith("http") else base + src
                res = await client.get(full_url)
                combined += res.text[:20000]  # 每個最多 20KB
            except:
                continue

    # Next.js SPA：也抓 _next/static/chunks/pages/ 的主要 chunk
    if "_next" in html or "next" in url.lower():
        chunks = re.findall(r'/_next/static/chunks/([^"\']+\.js)', html)
        for chunk in chunks[:3]:
            try:
                full_url = f"{base}/_next/static/chunks/{chunk}"
                async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
                    res = await client.get(full_url)
                    combined += res.text[:10000]
            except:
                continue

    return combined


async def analyze_tech_signals(html: str) -> dict:
    """技術追蹤訊號 — 呈現實際偵測到的追蹤碼與 SEO 數字"""
    if not html:
        return {}

    # 追蹤碼偵測
    gtm_ids = re.findall(r'GTM-[A-Z0-9]+', html)
    ga4_ids = re.findall(r'G-[A-Z0-9]+', html)
    aw_ids  = re.findall(r'AW-\d{9,12}', html)
    fb_ids  = re.findall(r'''fbq\(\s*['"]init['"]\s*,\s*['"](\d{10,20})['"]''', html)

    # SEO meta 分析
    kw_raw = re.search(r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    kw_list = [k.strip() for k in kw_raw.group(1).split(',') if k.strip()] if kw_raw else []

    meta_present = []
    for tag, pattern in [
        ("title",           r'<title[^>]*>[^<]+</title>'),
        ("description",     r'<meta[^>]+name=["\']description["\']'),
        ("keywords",        r'<meta[^>]+name=["\']keywords["\']'),
        ("og:title",        r'property=["\']og:title["\']'),
        ("og:description",  r'property=["\']og:description["\']'),
        ("og:image",        r'property=["\']og:image["\']'),
        ("canonical",       r'<link[^>]+rel=["\']canonical["\']'),
        ("robots",          r'<meta[^>]+name=["\']robots["\']'),
    ]:
        if re.search(pattern, html, re.I):
            meta_present.append(tag)

    # 結構化資料類型
    schema_types = re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html)
    schema_types = list(dict.fromkeys(schema_types))[:10]

    # 其他追蹤碼
    other_trackers = []
    for name, kw in [("Hotjar", "hotjar"), ("Clarity", "clarity.ms"), ("Criteo", "criteo"),
                     ("TikTok Pixel", "ttq."), ("LinkedIn Insight", 'linkedin.com/insight'),
                     ("AdRoll", "adroll"), ("Mixpanel", "mixpanel"), ("Segment", "analytics.js")]:
        if kw in html.lower():
            other_trackers.append(name)

    return {
        "gtm":              bool(gtm_ids),
        "gtm_ids":          list(dict.fromkeys(gtm_ids)),
        "meta_pixel":       bool(fb_ids) or "fbq(" in html,
        "meta_pixel_ids":   list(dict.fromkeys(fb_ids)),
        "ga4":              bool(ga4_ids) or "gtag(" in html,
        "ga4_ids":          list(dict.fromkeys(ga4_ids)),
        "google_ads_ids":   list(dict.fromkeys(aw_ids)),
        "remarketing":      any(kw in html.lower() for kw in ["remarketing", "retargeting", "adroll", "criteo"]),
        "other_trackers":   other_trackers,
        "seo_keyword_count": len(kw_list),
        "seo_keywords":     kw_list[:20],
        "meta_tags_present": meta_present,
        "meta_completeness": f"{len(meta_present)}/8",
        "structured_data":  bool(schema_types),
        "schema_types":     schema_types,
    }


async def check_meta_ads(html: str = "", scripts: str = "") -> dict:
    """
    偵測 Meta 廣告行為 — 從官網原始碼解析，不需要 API token。
    判斷依據：Meta Pixel 安裝、追蹤事件類型、再行銷設定。
    """
    full = (html or "") + " " + (scripts or "")
    result = {
        "available": bool(full.strip()),
        "has_ads": False,
        "has_pixel": False,
        "pixel_id": None,
        "pixel_events": [],
        "is_retargeting": False,
        "notes": [],
    }
    if not full.strip():
        return result

    # 1. 偵測 Meta Pixel 安裝
    has_pixel = (
        "fbq(" in full or
        "connect.facebook.net" in full or
        "_fbq" in full or
        "facebook.net/en_US/fbevents" in full
    )
    result["has_pixel"] = has_pixel
    if has_pixel:
        result["has_ads"] = True

        # 提取 Pixel ID
        pid = re.search(r'''fbq\(\s*['"]init['"]\s*,\s*['"](\d{10,20})['"]''', full)
        if pid:
            result["pixel_id"] = pid.group(1)

        # 偵測事件類型（代表實際有投放意圖）
        event_map = [
            ("Purchase",          "購買轉換"),
            ("InitiateCheckout",  "結帳意圖"),
            ("AddToCart",         "加入購物車"),
            ("ViewContent",       "商品瀏覽"),
            ("Lead",              "潛客收集"),
            ("CompleteRegistration", "完成註冊"),
            ("Search",            "站內搜尋"),
            ("PageView",          "頁面追蹤"),
        ]
        found_events = []
        for event, label in event_map:
            if (f"fbq('track', '{event}')" in full or
                    f'fbq("track", "{event}")' in full or
                    f"fbq('trackCustom', '{event}')" in full):
                found_events.append({"event": event, "label": label})
        result["pixel_events"] = found_events

        # 再行銷判斷：Custom Audience 或有多個轉換事件
        result["is_retargeting"] = (
            "CustomAudience" in full or
            "custom_audience" in full.lower() or
            len(found_events) >= 3 or
            "retarget" in full.lower()
        )

        # 加分提示
        active = [e for e in found_events if e["event"] in ("Purchase", "InitiateCheckout", "AddToCart")]
        if active:
            result["notes"].append(f"電商轉換事件：{', '.join(e['label'] for e in active)}")
        if result["is_retargeting"]:
            result["notes"].append("有再行銷受眾設定")

    return result


# ── 社群粉絲數解析 ─────────────────────────────────────────────────────────────

def _parse_count(raw: str) -> Optional[int]:
    """解析 '12.5K', '1.2M', '5,432' 等各種格式為整數"""
    if not raw:
        return None
    s = raw.strip().replace(',', '').replace(' ', '')
    try:
        if s[-1].lower() == 'k':
            return int(float(s[:-1]) * 1_000)
        elif s[-1].lower() == 'm':
            return int(float(s[:-1]) * 1_000_000)
        else:
            return int(float(s))
    except Exception:
        return None


async def _get_fb_followers(fb_url: str) -> Optional[int]:
    """嘗試從 Facebook 頁面抓追蹤人數"""
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
            r = await client.get(fb_url)
            text = r.text
        # JSON 結構化資料
        for pattern in [
            r'"follower_count":(\d+)',
            r'"followers_count":(\d+)',
            r'"subscriber_count":(\d+)',
        ]:
            m = re.search(pattern, text)
            if m:
                return int(m.group(1))
        # 頁面文字
        for pattern in [
            r'([\d,.]+[KkMm]?)\s*(?:人追蹤|位追蹤者|followers)',
            r'([\d,.]+[KkMm]?)\s*Followers',
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return _parse_count(m.group(1))
    except Exception as e:
        print(f"[signals] FB followers error: {e}")
    return None


async def _get_ig_followers(ig_url: str) -> Optional[int]:
    """嘗試從 Instagram 頁面抓追蹤人數（og:description 或 JSON）"""
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
            r = await client.get(ig_url)
            text = r.text
        # og:description: "12,345 Followers, 678 Following, 90 Posts"
        m = re.search(r'content="([^"]*(?:Followers|追蹤者)[^"]*)"', text, re.IGNORECASE)
        if m:
            fol = re.search(r'([\d,.]+[KkMm]?)\s*(?:Followers|追蹤者)', m.group(1), re.IGNORECASE)
            if fol:
                return _parse_count(fol.group(1))
        # JSON 結構
        m = re.search(r'"edge_followed_by":\{"count":(\d+)\}', text)
        if m:
            return int(m.group(1))
    except Exception as e:
        print(f"[signals] IG followers error: {e}")
    return None


async def fetch_social_followers(html: str) -> dict:
    """
    從官網 HTML 找出社群帳號連結，並嘗試取得粉絲/追蹤數。
    回傳各平台的 url 和 count。
    """
    result = {
        "facebook":  {"url": None, "count": None},
        "instagram": {"url": None, "count": None},
        "youtube":   {"url": None, "count": None},
    }
    if not html:
        return result

    # Facebook — 排除分享/登入等通用連結
    fb_m = re.search(
        r'https?://(?:www\.)?facebook\.com/(?!sharer|share\b|login|dialog|photo|posts|events|groups|watch|pages/create)([A-Za-z0-9_.%\-]+)',
        html
    )
    if fb_m:
        fb_url = fb_m.group(0).rstrip('/?')
        result["facebook"]["url"] = fb_url
        result["facebook"]["count"] = await _get_fb_followers(fb_url)

    # Instagram
    ig_m = re.search(r'https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?=["\'\s<])', html)
    if ig_m:
        ig_url = f"https://www.instagram.com/{ig_m.group(1)}/"
        result["instagram"]["url"] = ig_url
        result["instagram"]["count"] = await _get_ig_followers(ig_url)

    # YouTube — 嘗試抓訂閱數
    yt_m = re.search(r'https?://(?:www\.)?youtube\.com/(?:channel/|c/|@|user/)([A-Za-z0-9_.-]+)', html)
    if yt_m:
        yt_url = yt_m.group(0)
        result["youtube"]["url"] = yt_url
        result["youtube"]["count"] = await _get_yt_subscribers(yt_url)

    return result


async def check_google_ads(domain: str, html: Optional[str] = None) -> dict:
    """
    從官網原始碼偵測 Google Ads 相關 script。
    判斷依據：
    - Google Ads conversion tag (gtag('event', 'conversion') 或 AW- 開頭 ID)
    - Google Ads remarketing (google_ads_remarketing)
    - Google AdSense (adsbygoogle)
    - DoubleClick/DFP (doubleclick.net, googlesyndication)
    - Google Shopping feed (merchant_id)
    """
    signals = {
        "available": html is not None,
        "has_ads": False,
        "signals": []
    }
    if not html:
        return signals

    checks = [
        ("google_ads_conversion", r"AW-\d{9,12}", "Google Ads 轉換追蹤"),
        ("google_ads_remarketing", r"google_ads_remarketing|google_remarketing_only", "Google 再行銷"),
        ("adsense", r"adsbygoogle|pagead2\.googlesyndication", "Google AdSense"),
        ("doubleclick", r"doubleclick\.net|googletagservices\.com|googlesyndication\.com", "DoubleClick/DFP"),
        ("google_shopping", r"merchant_id|google\.com/shopping", "Google Shopping"),
        ("pmax_campaign", r"performance.max|pmax", "Performance Max"),
    ]

    found = []
    for key, pattern, label in checks:
        if re.search(pattern, html, re.IGNORECASE):
            found.append({"key": key, "label": label})

    signals["has_ads"] = len(found) > 0
    signals["signals"] = found
    signals["ad_types"] = [f["label"] for f in found]

    return signals


async def extract_social_signals(html: str) -> dict:
    if not html:
        return {}
    signals = {}
    # og:title
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html, re.IGNORECASE)
    if m:
        signals["og_title"] = m.group(1)[:200]

    # description
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.IGNORECASE)
    if m:
        signals["description"] = m.group(1)[:300]

    # og:description
    m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']', html, re.IGNORECASE)
    if m:
        signals["og_description"] = m.group(1)[:300]

    # title tag
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if m:
        signals["page_title"] = m.group(1).strip()[:200]

    # Social links
    signals["has_facebook"] = "facebook.com" in html
    signals["has_instagram"] = "instagram.com" in html
    signals["has_linkedin"] = "linkedin.com" in html
    signals["has_youtube"] = "youtube.com" in html

    return signals


async def analyze_operations_signals(html: str) -> dict:
    """積極營運訊號 — 呈現實際數字"""
    if not html:
        return {}
    h = html.lower()

    # 促銷關鍵字找哪些存在
    promo_map = {"特價": "特價", "優惠": "優惠", "折扣": "折扣", "限時": "限時",
                 "週年慶": "週年慶", "sale": "Sale", "discount": "Discount",
                 "promo": "Promo", "clearance": "清倉", "buy.*get": "買贈"}
    promo_found = [label for kw, label in promo_map.items() if re.search(kw, h)]

    # 商品頁數量估算：統計含商品路徑的連結數
    product_patterns = [r'/product[s]?/', r'/item/', r'/goods/', r'/shop/', r'/p/\d',
                        r'\?pid=', r'\?itemid=', r'/商品/', r'/產品/']
    product_urls = set()
    for pat in product_patterns:
        product_urls.update(re.findall(pat, h))
    product_links = len(re.findall(
        r'href=["\'][^"\']*(?:product|item|goods|商品|產品)[^"\']*["\']', html, re.I
    ))

    # 分類連結數量估算
    category_links = len(re.findall(
        r'href=["\'][^"\']*(?:category|cat|分類|系列)[^"\']*["\']', html, re.I
    ))

    # 影片數量
    video_count = len(re.findall(r'youtube\.com/embed|<video[^>]|\.mp4["\'\s]', html, re.I))

    # 部落格/文章數量估算
    blog_links = len(re.findall(
        r'href=["\'][^"\']*(?:blog|article|news|post|新聞|消息)[^"\']*["\']', html, re.I
    ))

    # 購物車/結帳功能
    cart_features = []
    for kw, label in [("加入購物車", "加入購物車"), ("add to cart", "Add to Cart"),
                      ("立即購買", "立即購買"), ("buy now", "Buy Now"),
                      ("checkout", "結帳"), ("立即訂購", "立即訂購")]:
        if kw in h:
            cart_features.append(label)

    return {
        "has_promotion":        bool(promo_found),
        "promotion_types":      promo_found,
        "has_product_page":     product_links > 0,
        "product_links_count":  product_links,
        "has_category":         category_links > 0,
        "category_links_count": category_links,
        "has_video":            video_count > 0,
        "video_count":          video_count,
        "has_blog_content":     blog_links > 0,
        "blog_links_count":     blog_links,
        "cart_features":        cart_features,
        "has_cart":             bool(cart_features),
        "has_structured_data":  "application/ld+json" in html or "schema.org" in html,
    }


async def _get_yt_subscribers(yt_url: str) -> Optional[int]:
    """嘗試從 YouTube 頻道頁面抓訂閱數"""
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
            r = await client.get(yt_url)
            text = r.text
        # YouTube 頁面 JSON
        for pattern in [
            r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"',
            r'"subscriberCountText":\{"runs":\[\{"text":"([^"]+)"',
            r'"shortSubscriberCountText":"([^"]+)"',
        ]:
            m = re.search(pattern, text)
            if m:
                raw = m.group(1).replace('位訂閱者', '').replace(' subscribers', '').strip()
                return _parse_count(raw)
    except Exception:
        pass
    return None


async def analyze_market_signals(html: str, domain: str) -> dict:
    """市場體量訊號 — 呈現實際數字"""
    if not html:
        return {}

    # 社群帳號連結
    fb_url  = (re.search(r'https?://(?:www\.)?facebook\.com/(?!sharer|share\b|login|dialog|photo|posts|events)([A-Za-z0-9_.%\-]+)', html) or [None])[0]
    ig_m    = re.search(r'https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?=["\'\s<])', html)
    yt_m    = re.search(r'https?://(?:www\.)?youtube\.com/(?:channel/|c/|@|user/)([A-Za-z0-9_.-]+)', html)
    li_m    = re.search(r'https?://(?:www\.)?linkedin\.com/company/([A-Za-z0-9_-]+)', html)

    social_urls = {
        "facebook":  fb_url,
        "instagram": f"https://www.instagram.com/{ig_m.group(1)}/" if ig_m else None,
        "youtube":   yt_m.group(0) if yt_m else None,
        "linkedin":  li_m.group(0) if li_m else None,
        "line":      bool("line.me" in html or "lin.ee" in html),
        "threads":   bool("threads.net" in html),
    }
    social_count = sum(1 for k, v in social_urls.items() if v and k not in ("line", "threads"))
    social_count += (1 if social_urls["line"] else 0) + (1 if social_urls["threads"] else 0)

    # SEO 指標
    title_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    title_len = len(title_m.group(1).strip()) if title_m else 0
    og_count = len(re.findall(r'property=["\']og:[^"\']+["\']', html, re.I))
    total_links = len(re.findall(r'<a[^>]+href=["\'][^"\']+["\']', html, re.I))

    # Sitemap
    sitemap_url_count = 0
    has_sitemap = False
    try:
        base = f"https://{domain}"
        async with httpx.AsyncClient(timeout=5, headers=HEADERS, follow_redirects=True) as client:
            r = await client.get(f"{base}/sitemap.xml")
            if r.status_code == 200 and "urlset" in r.text:
                has_sitemap = True
                sitemap_url_count = r.text.count("<url>")
    except Exception:
        pass

    return {
        "social_urls":         social_urls,
        "social_count":        social_count,
        "has_facebook":        bool(fb_url),
        "has_instagram":       bool(ig_m),
        "has_youtube":         bool(yt_m),
        "has_linkedin":        bool(li_m),
        "has_line":            social_urls["line"],
        "has_threads":         social_urls["threads"],
        "seo_title_length":    title_len,
        "og_tags_count":       og_count,
        "has_og_tags":         og_count > 0,
        "total_page_links":    total_links,
        "has_sitemap":         has_sitemap,
        "sitemap_url_count":   sitemap_url_count,
        "followers":           {},  # 由 fetch_social_followers 填入
    }


async def analyze_wallet_signals(
    html: str,
    domain: str,
    company_name: str = "",
    tax_id: str = "",
    stored_capital: str = "",
    stored_representative: str = "",
    notes: str = "",
) -> dict:
    """口袋深度訊號 — 呈現工商登記實際數字 + 廣告平台數量"""
    import urllib.parse

    signals = {
        "company_name_matched": None,
        "company_capital":      None,
        "company_capital_tw":   None,
        "company_status":       None,
        "company_representative": None,
        "established_date":     None,
        "business_items":       [],
        "ad_platform_count":    0,
        "ad_platforms_found":   [],
        "notes":                [],
    }

    # 優先使用 lead 上已儲存的資本額 / 代表人（從工商登記欄位或 notes 解析）
    cap_str = stored_capital or ""
    rep_str = stored_representative or ""

    # 若 capital_amount 欄位空白，嘗試從 notes 中解析（moeaic 爬蟲存為 "資本額：XXX萬"）
    if not cap_str and notes:
        m = re.search(r'資本額[：:]\s*([\d,.]+\s*萬?元?)', notes)
        if m:
            cap_str = m.group(1).strip()

    # 若 representative 欄位空白，從 notes 解析（moeaic 爬蟲存統編在 notes 但代表人在 contact_name）
    if not rep_str and notes:
        m = re.search(r'代表人[：:]\s*([^\s|｜]+)', notes)
        if m:
            rep_str = m.group(1).strip()

    # 從 notes 解析統一編號（若 tax_id 欄位為空）
    if not tax_id and notes:
        m = re.search(r'統編[：:]\s*(\d{8})', notes)
        if m:
            tax_id = m.group(1)

    if cap_str:
        signals["company_capital_tw"] = cap_str
        # 嘗試轉成數字 — 支援 "500萬" / "5,000,000元" / "500" 等格式
        digits = re.sub(r'[^\d]', '', cap_str)
        unit_match = re.search(r'(\d[\d,.]*)\s*(萬)', cap_str)
        if unit_match:
            try:
                signals["company_capital"] = int(float(unit_match.group(1).replace(',', '')) * 10000)
            except Exception:
                pass
        elif digits:
            try:
                signals["company_capital"] = int(digits)
            except Exception:
                pass
    if rep_str:
        signals["company_representative"] = rep_str

    # 工商登記查詢（使用正確的 236EE382 endpoint，以統編優先）
    GCIS_API = "https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C"

    async def _gcis_fetch(filter_expr: str, top: int = 1) -> list:
        """Build URL manually to keep '$' literal and properly encode Chinese."""
        filter_enc = urllib.parse.quote(filter_expr, safe="='% ")
        url = (
            f"{GCIS_API}?$format=json"
            f"&$filter={filter_enc}"
            f"&$top={top}"
            f"&$select=Company_Name,Business_Accounting_NO,Company_Status_Desc,Company_Setup_Date,Cmp_Business"
        )
        try:
            async with httpx.AsyncClient(timeout=10, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}) as client:
                r = await client.get(url)
                if r.status_code == 200 and r.text.strip().startswith("["):
                    return r.json()
        except Exception as e:
            signals["notes"].append(f"GCIS 查詢失敗: {str(e)[:60]}")
        return []

    gcis_data = None

    # 1. 用統一編號查詢（最準確）
    if tax_id and re.match(r'^\d{8}$', tax_id.strip()):
        result = await _gcis_fetch(f"Business_Accounting_NO eq {tax_id.strip()}", top=1)
        if result:
            gcis_data = result[0]

    # 2. 用公司名稱精確查詢
    if not gcis_data and company_name:
        result = await _gcis_fetch(f"Company_Name like '{company_name}'", top=1)
        if result:
            gcis_data = result[0]

    # 3. 用公司名稱模糊查詢（移除股份/有限後綴）
    if not gcis_data and company_name:
        short = re.sub(r'(股份有限公司|有限公司|有限責任公司|股份有限公司)$', '', company_name).strip()
        if short and short != company_name:
            result = await _gcis_fetch(f"Company_Name like '%{short}%'", top=3)
            if result:
                gcis_data = result[0]

    if gcis_data:
        signals["company_name_matched"] = gcis_data.get("Company_Name")
        signals["company_status"]       = gcis_data.get("Company_Status_Desc")
        raw_date = gcis_data.get("Company_Setup_Date", "")
        if raw_date and len(raw_date) == 7:
            # 民國年 YYYMMDD → 西元
            try:
                roc_year = int(raw_date[:3])
                month    = raw_date[3:5]
                day      = raw_date[5:7]
                signals["established_date"] = f"{roc_year + 1911}-{month}-{day}"
            except Exception:
                signals["established_date"] = raw_date
        biz = gcis_data.get("Cmp_Business") or []
        signals["business_items"] = [b.get("Business_Item_Desc", "") for b in biz[:8] if b.get("Business_Item_Desc")]

    # 廣告平台偵測（實際數量，不估算預算）
    if html:
        h = html.lower()
        platform_checks = [
            ("Google Tag Manager",  "googletagmanager"),
            ("Meta Pixel",          "fbq("),
            ("GA4 / gtag",          "gtag("),
            ("Google Ads",          re.search(r"AW-\d{9,12}", html)),
            ("Criteo",              "criteo"),
            ("TikTok Pixel",        "ttq."),
            ("LinkedIn Insight",    "linkedin" in h and "insight" in h),
            ("AdRoll",              "adroll"),
            ("Hotjar",              "hotjar"),
            ("Clarity",             "clarity.ms"),
        ]
        found_platforms = []
        for name, check in platform_checks:
            hit = check if isinstance(check, bool) else (check if not isinstance(check, str) else check in h)
            if hit:
                found_platforms.append(name)
        signals["ad_platforms_found"] = found_platforms
        signals["ad_platform_count"]  = len(found_platforms)

    return signals


def calculate_enriched_score(tech: dict, ad: dict, social: dict,
                              ops: dict = None, market: dict = None, wallet: dict = None) -> tuple:
    score = 0
    breakdown = {}

    # 1. 技術追蹤（30分）
    tech_score = 0
    if tech.get("gtm"):         tech_score += 8
    if tech.get("meta_pixel"):  tech_score += 10
    if tech.get("ga4"):         tech_score += 7
    if tech.get("remarketing"): tech_score += 5
    breakdown["技術追蹤"] = {"score": tech_score, "max": 30}
    score += tech_score

    # 2. 廣告投放（30分）
    ad_score = 0
    meta = ad.get("meta", {})
    # Meta Pixel（最高15分）：有 Pixel = 8, 有轉換事件 = +4, 有再行銷 = +3
    if meta.get("has_pixel"):
        ad_score += 8
        events = meta.get("pixel_events", [])
        if any(e["event"] in ("Purchase", "InitiateCheckout", "AddToCart") for e in events):
            ad_score += 4
        if meta.get("is_retargeting"):
            ad_score += 3
    # Google Ads（最高15分）
    google_sigs = ad.get("google_ads", {}).get("signals", [])
    if google_sigs:
        ad_score += min(len(google_sigs) * 5, 15)
    elif ad.get("google_ads", {}).get("has_ads"):
        ad_score += 10
    breakdown["廣告投放"] = {"score": ad_score, "max": 30,
                            "meta_pixel": meta.get("has_pixel", False),
                            "pixel_events": [e["label"] for e in meta.get("pixel_events", [])]}
    score += ad_score

    # 3. 積極營運（20分）
    ops_score = 0
    if ops:
        if ops.get("has_promotion"):        ops_score += 6
        if ops.get("has_product_page"):     ops_score += 5
        if ops.get("has_video"):            ops_score += 4
        if ops.get("seo_meta_complete"):    ops_score += 3
        if ops.get("has_structured_data"):  ops_score += 2
    breakdown["積極營運"] = {"score": ops_score, "max": 20}
    score += ops_score

    # 4. 市場體量（15分）= 社群平台數(最高6) + OG/Sitemap(最高4) + 粉絲數(最高5)
    market_score = 0
    if market:
        social_count = market.get("social_count", 0)
        market_score += min(social_count * 2, 6)
        if market.get("has_og_tags"):   market_score += 2
        if market.get("has_sitemap"):   market_score += 2
        # 粉絲數加分
        followers = market.get("followers", {})
        fb_n  = followers.get("facebook",  {}).get("count") or 0
        ig_n  = followers.get("instagram", {}).get("count") or 0
        max_f = max(fb_n, ig_n)
        if   max_f >= 100_000: market_score += 5
        elif max_f >= 10_000:  market_score += 3
        elif max_f >= 1_000:   market_score += 1
    breakdown["市場體量"] = {"score": market_score, "max": 15,
                            "followers": market.get("followers", {}) if market else {}}
    score += market_score

    # 5. 口袋深度（5分）
    wallet_score = 0
    if wallet:
        if wallet.get("company_capital"):
            cap = wallet["company_capital"]
            if cap >= 50_000_000:   wallet_score += 5   # 5000萬以上
            elif cap >= 10_000_000: wallet_score += 3   # 1000萬以上
            elif cap >= 1_000_000:  wallet_score += 1
        elif wallet.get("estimated_ad_budget") and "高" in str(wallet.get("estimated_ad_budget", "")):
            wallet_score += 3
    breakdown["口袋深度"] = {"score": wallet_score, "max": 5}
    score += wallet_score

    return min(score, 100), breakdown


@router.post("/{lead_id}/signals/analyze", response_model=SignalsResponse)
async def analyze_signals(
    lead_id: UUID,
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 優先順序：手動填入 > lead.website > email domain 推測
    inferred = None
    website_url = body.website_url or lead.website
    if not website_url and lead.email and "@" in lead.email:
        email_domain = lead.email.split("@")[1]
        free_domains = {"gmail.com", "yahoo.com", "yahoo.com.tw", "hotmail.com",
                        "outlook.com", "icloud.com", "msn.com", "live.com", "163.com", "qq.com"}
        if email_domain not in free_domains:
            website_url = f"https://{email_domain}"
            inferred = website_url
            # 自動回填 lead.website
            lead.website = website_url
            db.commit()

    if not website_url:
        raise HTTPException(status_code=400, detail="No website URL provided")

    domain = extract_domain(website_url)

    # Fetch HTML + JS scripts
    html = await fetch_website_html(website_url)
    scripts = await fetch_website_scripts(website_url, html or "")
    full_content = (html or "") + " " + scripts

    # Analyze all signals（Meta 改為從 HTML 偵測 Pixel，不再呼叫需要 token 的 API）
    tech       = await analyze_tech_signals(full_content)
    meta_ads   = await check_meta_ads(html=full_content, scripts=scripts)
    google_ads = await check_google_ads(domain, full_content)
    social     = await extract_social_signals(html or "")
    ops        = await analyze_operations_signals(full_content)
    market     = await analyze_market_signals(html or "", domain)
    wallet     = await analyze_wallet_signals(
        html=full_content,
        domain=domain,
        company_name=lead.company_name or "",
        tax_id=lead.tax_id or "",
        stored_capital=lead.capital_amount or "",
        stored_representative=lead.representative_name or "",
        notes=lead.notes or "",
    )

    # 粉絲數：從官網 HTML 找社群帳號再抓追蹤數
    followers  = await fetch_social_followers(html or "")
    market["followers"] = followers  # 加入 market signals

    # Combine ad signals
    ad_signals = {
        "meta": meta_ads,
        "google_ads": google_ads,
        "has_ads": meta_ads.get("has_ads", False) or google_ads.get("has_ads", False),
    }

    score, breakdown = calculate_enriched_score(tech, ad_signals, social, ops, market, wallet)

    # Update lead — 各訊號分別存入獨立欄位
    lead.tech_signals = tech
    lead.ad_signals = ad_signals
    lead.social_signals = social          # 純社群數據
    lead.ops_signals = ops                # 積極營運訊號
    lead.market_signals = market          # 市場體量訊號
    lead.wallet_signals = wallet          # 口袋深度訊號（原本漏存）
    lead.enriched_score = score
    db.commit()

    return SignalsResponse(
        tech_signals=tech,
        ad_signals=ad_signals,
        social_signals=social,
        operations_signals=ops,
        market_signals=market,
        wallet_signals=wallet,
        enriched_score=score,
        score_breakdown=breakdown,
        inferred_website=inferred,
    )


# Batch analyze endpoint
class BatchAnalyzeRequest(BaseModel):
    lead_ids: list[str] = []
    all_with_website: bool = False


@router.post("/signals/batch-analyze")
async def batch_analyze_signals(
    body: BatchAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Batch analyze signals for multiple leads."""
    if body.all_with_website:
        # 有 website 或有非免費 email 的名單都跑
        from sqlalchemy import or_
        free_domains_like = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
        leads = db.query(Lead).filter(
            or_(
                Lead.website.isnot(None),
                Lead.email.isnot(None)
            )
        ).all()
        # 過濾免費信箱（沒有 website 才需要推測）
        leads = [l for l in leads if l.website or (
            l.email and "@" in l.email and
            l.email.split("@")[1] not in {"gmail.com","yahoo.com","yahoo.com.tw","hotmail.com","outlook.com","icloud.com"}
        )]
    else:
        leads = db.query(Lead).filter(Lead.id.in_(body.lead_ids)).all()

    results = []
    for lead in leads[:20]:  # Limit to 20 per batch
        try:
            website_url = lead.website
            # 與單筆一致：無 website 時從 email domain 推測
            if not website_url and lead.email and "@" in lead.email:
                email_domain = lead.email.split("@")[1]
                free_domains = {"gmail.com","yahoo.com","yahoo.com.tw","hotmail.com",
                                "outlook.com","icloud.com","msn.com","live.com"}
                if email_domain not in free_domains:
                    website_url = f"https://{email_domain}"
                    lead.website = website_url
            if not website_url:
                continue
            domain = extract_domain(website_url)
            html = await fetch_website_html(website_url)
            scripts = await fetch_website_scripts(website_url, html or "")
            full_content = (html or "") + " " + scripts
            tech      = await analyze_tech_signals(full_content)
            meta_ads  = await check_meta_ads(html=full_content, scripts=scripts)
            google_ads = await check_google_ads(domain, full_content)
            social    = await extract_social_signals(html or "")
            ops       = await analyze_operations_signals(full_content)
            market    = await analyze_market_signals(html or "", domain)
            followers = await fetch_social_followers(html or "")
            market["followers"] = followers
            wallet = await analyze_wallet_signals(
                html=full_content,
                domain=domain,
                company_name=lead.company_name or "",
                tax_id=lead.tax_id or "",
                stored_capital=lead.capital_amount or "",
                stored_representative=lead.representative_name or "",
                notes=lead.notes or "",
            )
            ad_signals = {
                "meta": meta_ads,
                "google_ads": google_ads,
                "has_ads": meta_ads.get("has_ads", False) or google_ads.get("has_ads", False),
            }
            score, breakdown = calculate_enriched_score(tech, ad_signals, social, ops, market, wallet)
            lead.tech_signals = tech
            lead.ad_signals = ad_signals
            lead.social_signals = social
            lead.ops_signals = ops
            lead.market_signals = market
            lead.wallet_signals = wallet
            lead.enriched_score = score
            results.append({"lead_id": str(lead.id), "company": lead.company_name, "score": score, "breakdown": breakdown})
        except Exception as e:
            results.append({"lead_id": str(lead.id), "company": lead.company_name, "error": str(e)})

    db.commit()
    return {"processed": len(results), "results": results}
