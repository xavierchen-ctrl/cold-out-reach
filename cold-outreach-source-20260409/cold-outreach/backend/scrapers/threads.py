"""
Threads 爬蟲
搜尋 Threads 上的品牌/KOL 帳號，從個人簡介抓取聯絡資訊。
Threads 為 JS 渲染，使用 Playwright。
URL 格式: https://www.threads.net/search?q=關鍵字&serp_type=default
"""
import asyncio
import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

_SYSTEM_EMAIL_PREFIXES = [
    "noreply", "no-reply", "donotreply", "webmaster", "postmaster",
]

_PW_LAUNCH_ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox",
    "--disable-dev-shm-usage", "--disable-gpu", "--ignore-certificate-errors",
]


def _extract_contact_info(text: str) -> Tuple[Optional[str], Optional[str]]:
    """從文字中抽取電話和 Email"""
    email = None
    phone = None

    for m in re.finditer(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text):
        e = m.group(0).lower()
        if not any(e.startswith(p) for p in _SYSTEM_EMAIL_PREFIXES):
            email = m.group(0)
            break

    phone_patterns = [
        r"\(?0[2-9]\d{0,2}\)?[-\s]?\d{3,4}[-\s]?\d{4}",
        r"0[2-9]\d{0,2}[-\s\.]\d{3,4}[-\s\.]\d{4}",
        r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}",
        r"\+886[-\s]?[2-9]\d{0,1}[-\s]?\d{3,4}[-\s]?\d{4}",
    ]
    for pat in phone_patterns:
        m = re.search(pat, text)
        if m:
            phone = re.sub(r"\s+", "", m.group(0))
            break

    return phone, email


def _extract_url_from_text(text: str) -> Optional[str]:
    """從文字中抽取 URL（官網）"""
    m = re.search(
        r"https?://(?:www\.)?(?!threads\.net|instagram\.com|facebook\.com|twitter\.com|x\.com)"
        r"[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[^\s\]\"'<>]*",
        text,
    )
    if m:
        return m.group(0).rstrip(".,;)")
    # www. 開頭但沒有 https://
    m2 = re.search(r"www\.[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[^\s\]\"'<>]*", text)
    if m2:
        return "https://" + m2.group(0).rstrip(".,;)")
    return None


async def _scrape_with_playwright(url: str, keyword: str, limit: int) -> List[dict]:
    """用 Playwright 搜尋 Threads 並抓取帳號資訊"""
    results = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=_PW_LAUNCH_ARGS)
            ctx = await browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                locale="zh-TW",
                viewport={"width": 1280, "height": 900},
                ignore_https_errors=True,
            )
            page = await ctx.new_page()

            logger.info(f"Threads: loading search page {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning(f"Threads: page load error: {e}")
                await browser.close()
                return []

            html = await page.content()

            # 偵測登入牆
            login_markers = [
                "Log in", "登入", "Sign in", "Create an account",
                "You need to log in", "Join Threads",
            ]
            if any(m in html for m in login_markers) and "search" not in html.lower():
                logger.warning("Threads: login wall detected, results may be limited")

            # 嘗試滾動載入更多結果
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            html = await page.content()

            # 抓取搜尋結果中的帳號卡片
            # Threads search 結果：每個帳號卡片含 username、display name、bio
            seen_usernames = set()

            # 策略 A：抓 a[href^="/@"] 連結（個人主頁連結）
            profile_links = await page.query_selector_all('a[href^="/@"]')
            profile_urls = []
            for link in profile_links:
                href = await link.get_attribute("href")
                if href and href not in profile_urls:
                    profile_urls.append(href)

            logger.info(f"Threads: found {len(profile_urls)} profile links")

            # 對每個個人主頁連結，提取帳號資訊
            for href in profile_urls[:limit]:
                username = href.lstrip("/@").split("/")[0].split("?")[0]
                if not username or username in seen_usernames:
                    continue
                seen_usernames.add(username)

                # 嘗試從搜尋結果頁抓取 bio（不進入個人頁）
                # 從整頁 HTML 用 regex 找 username 附近的文字
                bio_text = ""
                phone, email, website = None, None, None

                # 進入個人主頁取得 bio
                if len(results) < limit:
                    try:
                        profile_url = f"https://www.threads.net/@{username}"
                        await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
                        await page.wait_for_timeout(2000)
                        profile_html = await page.content()

                        # 從 meta description 抓 bio（Threads 會把 bio 放在 og:description）
                        m_desc = re.search(
                            r'<meta[^>]+(?:name="description"|property="og:description")[^>]+content="([^"]*)"',
                            profile_html,
                        )
                        if m_desc:
                            bio_text = m_desc.group(1)

                        # 也嘗試從 JSON-LD 或其他結構化資料抓
                        if not bio_text:
                            m_json = re.search(r'"biography"\s*:\s*"([^"]*)"', profile_html)
                            if m_json:
                                bio_text = m_json.group(1)

                        # 從 page title 抓 display name
                        m_title = re.search(r"<title>([^<]+)</title>", profile_html)
                        display_name = username
                        if m_title:
                            title_text = m_title.group(1)
                            # "Display Name (@username) • Threads"
                            m_dn = re.match(r"^(.+?)\s*\(@", title_text)
                            if m_dn:
                                display_name = m_dn.group(1).strip()

                        if bio_text:
                            phone, email = _extract_contact_info(bio_text)
                            website = _extract_url_from_text(bio_text)

                        results.append({
                            "company_name": display_name,
                            "contact_name": f"@{username}",
                            "title": None,
                            "email": email,
                            "phone": phone,
                            "website": website,
                            "industry": None,
                            "city": None,
                            "company_size": None,
                            "source": "threads",
                            "source_url": profile_url,
                            "notes": bio_text[:200] if bio_text else None,
                        })
                        logger.info(
                            f"Threads @{username}: email={email!r} phone={phone!r} web={website!r}"
                        )
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.warning(f"Threads profile @{username} error: {e}")
                        # 仍加入基本資料
                        results.append({
                            "company_name": username,
                            "contact_name": f"@{username}",
                            "title": None,
                            "email": None,
                            "phone": None,
                            "website": None,
                            "industry": None,
                            "city": None,
                            "company_size": None,
                            "source": "threads",
                            "source_url": f"https://www.threads.net/@{username}",
                            "notes": None,
                        })

            await browser.close()

    except Exception as e:
        logger.error(f"Threads scraper error: {e}")

    return results


async def _scrape_posts_with_playwright(url: str, limit: int, session_cookie: str = None) -> List[dict]:
    """爬取 Threads 貼文搜尋結果（serp_type=posts），含讚數/轉發/留言"""
    results = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=_PW_LAUNCH_ARGS + ["--disable-blink-features=AutomationControlled"],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="zh-TW",
                viewport={"width": 1366, "height": 768},
                ignore_https_errors=True,
                extra_http_headers={
                    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
            )
            # 注入 sessionid cookie（如果使用者有設定）
            if session_cookie:
                await ctx.add_cookies([{
                    "name": "sessionid",
                    "value": session_cookie.strip(),
                    "domain": ".threads.net",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                }])
                logger.info("Threads posts: sessionid cookie injected")

            page = await ctx.new_page()

            # 隱藏 webdriver 特徵（反 bot 偵測）
            await page.add_init_script("""
                delete Object.getPrototypeOf(navigator).webdriver;
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh','en-US','en']});
                window.chrome = {runtime: {}};
            """)

            logger.info(f"Threads posts: loading {url}")
            # 未登入時先造訪首頁建立 session；已有 cookie 時直接去搜尋頁
            if not session_cookie:
                try:
                    await page.goto("https://www.threads.net/", wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)
            except Exception as e:
                logger.warning(f"Threads posts: page load error: {e}")
                await browser.close()
                return []

            # 滾動載入更多貼文
            for _ in range(6):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1800)

            html = await page.content()
            logger.info(f"Threads posts: page html size={len(html)}, has_article={'article' in html.lower()}")

            # 策略 1：DOM 選取器（多層fallback）
            posts = await page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();

                    // 多種 container 選取器
                    const selectors = [
                        'article',
                        '[role="article"]',
                        '[role="listitem"]',
                        'div[data-pressable-container]',
                    ];

                    let containers = [];
                    for (const sel of selectors) {
                        const found = Array.from(document.querySelectorAll(sel));
                        if (found.length > 0) { containers = found; break; }
                    }

                    // fallback：找所有含 /@username 連結的父 div
                    if (containers.length === 0) {
                        const allAuthorLinks = document.querySelectorAll('a[href^="/@"]');
                        const parents = new Set();
                        for (const link of allAuthorLinks) {
                            let p = link.parentElement;
                            for (let i = 0; i < 6 && p; i++, p = p.parentElement) {
                                if ((p.textContent || '').length > 80) { parents.add(p); break; }
                            }
                        }
                        containers = Array.from(parents);
                    }

                    for (const container of containers) {
                        try {
                            const authorLink = container.querySelector('a[href^="/@"]');
                            if (!authorLink) continue;

                            const href = authorLink.getAttribute('href') || '';
                            const username = href.replace(/^\\/@/, '').split('/')[0].split('?')[0];
                            if (!username) continue;

                            const dedupKey = username + '|' + (container.textContent || '').substring(0, 40);
                            if (seen.has(dedupKey)) continue;
                            seen.add(dedupKey);

                            // 顯示名稱
                            let displayName = username;
                            const nameEl = authorLink.querySelector('span, strong, b');
                            if (nameEl && nameEl.textContent) displayName = nameEl.textContent.trim();

                            // 貼文文字：找最長非UI段落
                            let postText = '';
                            let maxLen = 0;
                            for (const el of container.querySelectorAll('span, p, div')) {
                                if (el.childElementCount > 6) continue;
                                const t = (el.textContent || '').trim();
                                const isUI = /^(\\d+\\s*(likes?|reposts?|replies|留言|讚|轉發)|log in|join|sign)/i.test(t);
                                if (!isUI && t.length > maxLen && t.length > 20) {
                                    maxLen = t.length;
                                    postText = t;
                                }
                            }

                            // 互動數
                            let likes = 0, reposts = 0, replies = 0;
                            for (const btn of container.querySelectorAll('[aria-label]')) {
                                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                                const m = label.match(/(\\d[\\d,]*)/);
                                const n = m ? parseInt(m[1].replace(/,/g, '')) : 0;
                                if (label.includes('like') || label.includes('讚')) likes = n;
                                else if (label.includes('repost') || label.includes('rethread') || label.includes('轉')) reposts = n;
                                else if (label.includes('repl') || label.includes('留言') || label.includes('comment')) replies = n;
                            }

                            // 貼文連結
                            let postUrl = '';
                            const pl = container.querySelector('a[href*="/post/"]');
                            if (pl) postUrl = 'https://www.threads.net' + pl.getAttribute('href');

                            results.push({ username, displayName, postText: postText.substring(0, 600), likes, reposts, replies, postUrl });
                        } catch(e) {}
                    }
                    return results;
                }
            """)

            # 策略 2：從 HTML 中提取嵌入的 JSON 資料
            if not posts:
                logger.info("Threads posts: DOM strategy got 0, trying JSON extraction from HTML")
                posts = _extract_posts_from_html(html)

            await browser.close()
            logger.info(f"Threads posts: final extracted {len(posts)} posts")

            for post in posts[:limit]:
                username = post.get('username', '')
                post_text = post.get('postText', '') or post.get('post_text', '')
                post_url = post.get('postUrl') or post.get('post_url') or f"https://www.threads.net/@{username}"
                results.append({
                    "company_name": post.get('displayName') or post.get('display_name') or username,
                    "contact_name": f"@{username}",
                    "email": None,
                    "phone": None,
                    "website": post_url,
                    "industry": None,
                    "city": None,
                    "company_size": None,
                    "title": None,
                    "source": "threads_posts",
                    "source_url": post_url,
                    "post_text": post_text,
                    "likes": post.get('likes', 0),
                    "reposts": post.get('reposts', 0),
                    "replies": post.get('replies', 0),
                    "notes": post_text[:300] if post_text else None,
                })

    except Exception as e:
        logger.error(f"Threads posts scraper error: {e}")

    return results


def _extract_posts_from_html(html: str) -> list:
    """從 Threads 頁面 HTML 嘗試提取 JSON 嵌入的貼文資料"""
    import json as _json
    posts = []
    try:
        # 找所有 <script> 內的 JSON
        for m in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
            content = m.group(1).strip()
            if not content or len(content) < 50:
                continue
            try:
                data = _json.loads(content)
                # 遞迴找 post-like 結構
                _collect_posts_from_json(data, posts)
                if len(posts) >= 50:
                    break
            except Exception:
                pass

        # 也找 window.__META__ 或 require("TimeSliceImpl")(...) 格式
        for m in re.finditer(r'"text_post_app_thread".*?"text"\s*:\s*"([^"]{20,})"', html):
            posts.append({
                "username": "unknown",
                "displayName": "unknown",
                "postText": m.group(1)[:500],
                "likes": 0, "reposts": 0, "replies": 0,
                "postUrl": "",
            })
    except Exception as e:
        logger.warning(f"_extract_posts_from_html error: {e}")
    return posts[:50]


def _collect_posts_from_json(obj, out: list, depth: int = 0):
    if depth > 10 or len(out) > 50:
        return
    if isinstance(obj, dict):
        # Threads 貼文特徵：有 username + body_text 或 caption
        username = obj.get('username') or obj.get('user', {}).get('username', '') if isinstance(obj.get('user'), dict) else ''
        text = obj.get('caption') or obj.get('body_text') or obj.get('text') or ''
        if username and text and len(str(text)) > 15:
            out.append({
                "username": str(username),
                "displayName": obj.get('full_name') or (obj.get('user', {}).get('full_name', '') if isinstance(obj.get('user'), dict) else '') or username,
                "postText": str(text)[:600],
                "likes": obj.get('like_count') or obj.get('likes') or 0,
                "reposts": obj.get('repost_count') or obj.get('reposts') or 0,
                "replies": obj.get('reply_count') or obj.get('replies') or 0,
                "postUrl": f"https://www.threads.net/@{username}",
            })
            return
        for v in obj.values():
            _collect_posts_from_json(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _collect_posts_from_json(item, out, depth + 1)


async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 20, cookies_str: str = None, **kwargs) -> List[dict]:
    """
    搜尋 Threads 帳號並回傳聯絡資訊。
    url: Threads 搜尋 URL，如 https://www.threads.net/search?q=數位行銷&serp_type=default
         或帳號主頁 URL，如 https://www.threads.net/@brand_name
    """
    lim = min(limit or 20, 50)

    # 如果是帳號主頁（/@username），直接抓單一帳號
    parsed = urlparse(url)
    if parsed.path.startswith("/@"):
        username = parsed.path.lstrip("/@").split("/")[0]
        kw = keyword or username
        search_url = f"https://www.threads.net/search?q={kw}&serp_type=default"
    else:
        search_url = url

    # keyword 優先覆蓋 URL 中的 q 參數
    if keyword:
        # 保留現有的 serp_type
        serp_type = "posts" if "serp_type=posts" in search_url else "default"
        search_url = re.sub(r"[?&]q=[^&]*", "", search_url)
        sep = "&" if "?" in search_url else "?"
        search_url = f"{search_url}{sep}q={keyword}&serp_type={serp_type}"

    # 貼文模式 (serp_type=posts)
    is_posts_mode = "serp_type=posts" in search_url

    if is_posts_mode:
        logger.info(f"Threads posts mode: url={search_url}, limit={lim}, has_cookie={bool(cookies_str)}")
        results = await _scrape_posts_with_playwright(search_url, lim, session_cookie=cookies_str)
    else:
        logger.info(f"Threads accounts mode: url={search_url}, limit={lim}")
        results = await _scrape_with_playwright(search_url, keyword or "", lim)

    # 帳號模式才做 keyword 篩選（貼文模式搜尋結果本身就已過濾）
    if not is_posts_mode and keyword and results:
        kw_lower = keyword.lower()
        filtered = [
            r for r in results
            if kw_lower in (r.get("company_name") or "").lower()
            or kw_lower in (r.get("notes") or "").lower()
            or kw_lower in (r.get("contact_name") or "").lower()
        ]
        if filtered:
            results = filtered

    if industry:
        for r in results:
            if not r.get("industry"):
                r["industry"] = industry

    logger.info(f"Threads scrape done: {len(results)} results")
    return results[:lim]
