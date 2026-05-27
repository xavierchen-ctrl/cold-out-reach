"""
通用展覽/目錄網頁爬蟲
三層邏輯：
  第一層：列表頁  → 公司名稱 + 詳情連結 + 可能的官網/電話/Email
  第二層：詳情頁  → 官網/電話/Email（若第一層沒抓到）
  第三層：官網    → 電話/Email（首頁 + 聯絡/關於頁）
"""
import httpx
import re
import logging
import asyncio
import urllib.parse
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── 常數設定 ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,*/*",
}

# 社群/平台/CDN 等非公司官網 domain
BLACKLISTED_DOMAINS = {
    'facebook.com', 'fb.com', 'twitter.com', 'x.com', 'instagram.com',
    'youtube.com', 'linkedin.com', 'google.com', 'googleapis.com',
    'line.me', 'tiktok.com', 'threads.net', 'threads.com',
    'shopee.tw', 'shopee.com', 'ruten.com.tw', 'pchome.com.tw',
    'yahoo.com', 'yahoo.com.tw', 'amazon.com', 'amazon.com.tw',
    'cloudfront.net', 'amazonaws.com', 'cdn.', 'cloudflare.com',
    'bootstrap', 'jquery.com', 'fontawesome.com',
    'gov.tw', 'moc.gov.tw',  # 政府機關不是廠商官網
}

# 台灣公司名稱常見結尾（用於判斷是否為公司名稱）
COMPANY_SUFFIXES = (
    # 公司類
    '有限公司', '股份有限公司', '企業有限公司', '企業股份有限公司',
    '實業有限公司', '實業股份有限公司', '國際有限公司', '國際股份有限公司',
    '工業有限公司', '工業股份有限公司', '科技有限公司', '科技股份有限公司',
    '貿易有限公司', '貿易股份有限公司', '投資有限公司', '投資股份有限公司',
    '顧問有限公司', '顧問股份有限公司', '行銷有限公司', '行銷股份有限公司',
    '廣告有限公司', '廣告股份有限公司', '文化有限公司', '文化股份有限公司',
    '出版有限公司', '出版股份有限公司', '媒體有限公司', '媒體股份有限公司',
    '設計有限公司', '設計股份有限公司', '整合有限公司', '整合股份有限公司',
    '傳播有限公司', '傳播股份有限公司',
    # 簡短結尾
    '公司', '集團', '旅行社', '航空公司', '航空', '酒廠', '銀行',
    '書局', '出版社', '出版', '文化', '基金會',
    # 法人/協會
    '協會', '公會', '財團法人', '社團法人', '研究院', '學會',
    # 英文
    'Ltd.', 'Ltd', 'Co., Ltd.', 'Co.,Ltd.', 'Inc.', 'Corp.', 'LLC', 'Limited',
)

# 聯絡頁面關鍵字
CONTACT_PAGE_HINTS = [
    'contact', 'about', '聯絡', '關於', 'contactus', 'about-us',
    'service', 'support', '客服', '服務', 'us.html', 'info',
]

# 官網欄位關鍵字
WEBSITE_KEYWORDS = ['官網', '官方網站', '公司網址', 'Website', 'website', '網站', 'Official', '官方']

# 系統/無效 Email 前綴
SYSTEM_EMAIL_PREFIXES = ['noreply', 'no-reply', 'donotreply', 'webmaster', 'postmaster', 'mailer-daemon']


# ── 工具函數 ──────────────────────────────────────────────────────────────────

def get_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        return domain[4:] if domain.startswith('www.') else domain
    except Exception:
        return ''


def normalize_url(href: str, base_url: str = '') -> str:
    """正規化 URL：補 https://、去追蹤參數、轉絕對路徑"""
    if not href:
        return ''
    href = href.strip()
    # 補前綴
    if href.startswith('www.'):
        href = 'https://' + href
    elif not href.startswith('http') and base_url:
        href = urllib.parse.urljoin(base_url, href)
    if not href.startswith('http'):
        return ''
    # 去掉追蹤參數（?income=1, ?utm_source=... 等）
    parsed = urllib.parse.urlparse(href)
    # 保留必要的 query 參數（如分頁），過濾追蹤用參數
    if parsed.query:
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        tracking = {'income', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
                    'utm_term', 'fbclid', 'gclid', 'ref', 'from', 'source'}
        clean_params = {k: v for k, v in params.items() if k.lower() not in tracking}
        clean_query = urllib.parse.urlencode(clean_params, doseq=True)
        href = urllib.parse.urlunparse(parsed._replace(query=clean_query))
    return href.rstrip('/')


def is_company_website(url: str, source_domain: str = '') -> bool:
    """判斷 URL 是否為公司官網（非社群/CDN/來源展覽網站）"""
    if not url or not url.startswith('http'):
        return False
    domain = get_domain(url)
    if not domain:
        return False
    # 排除黑名單
    for bl in BLACKLISTED_DOMAINS:
        if domain == bl or domain.endswith('.' + bl) or bl in domain:
            return False
    # 排除來源網站本身
    if source_domain and (domain == source_domain or domain.endswith('.' + source_domain)):
        return False
    return True


def clean_company_name(raw: str) -> str:
    """
    從中英混合名稱中提取中文公司名稱。
    例：'三采文化股份有限公司 SUN COLOR CO., LTD.' → '三采文化股份有限公司'
        '允晨文化 Asian Culture Co., Ltd.'       → '允晨文化'
        'San Min Book Co., Ltd.'                → 'San Min Book Co., Ltd.'（純英文保留）
    """
    raw = raw.strip()
    # 有中文的情況：找中文結束、英文開始的位置
    if re.search(r'[一-鿿]', raw):
        # 找第一個「空格後接英文大寫或拼音」的位置
        m = re.search(r'\s+[A-Za-z]', raw)
        if m:
            return raw[:m.start()].strip()
    return raw


def is_company_name(name: str) -> bool:
    """
    判斷字串是否像公司名稱。
    支援：中文名稱、中英混合（只取中文部分）、純英文（大小寫不敏感）
    """
    # 先嘗試提取純中文公司名稱
    clean = clean_company_name(name)
    # 中文後綴（大小寫精確）
    for suffix in COMPANY_SUFFIXES:
        if clean.endswith(suffix):
            return True
    # 英文後綴（大小寫不敏感）
    name_lower = clean.lower()
    for suffix in ['ltd.', 'ltd', 'co., ltd.', 'co.,ltd.', 'inc.', 'corp.',
                   'llc', 'limited', 'corporation', 'company']:
        if name_lower.endswith(suffix):
            return True
    # 包含 company / corporation 關鍵字（不限位置）
    for kw in ['company', 'corporation']:
        if kw in name_lower:
            return True
    return False


def extract_contact_info(text: str, source_domain: str = '') -> Tuple[Optional[str], Optional[str]]:
    """
    從文字中抽取電話和 Email。
    source_domain: 展覽/目錄網站的 domain，用於過濾來源網站自己的 email。
    注意：不過濾公司自己官網的 email（呼叫端自行決定是否要這個 email）
    """
    phone = None
    email = None

    # Email（不過濾公司 domain，只過濾系統信箱）
    email_m = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    if email_m:
        e = email_m.group(0).lower()
        is_system = any(e.startswith(p) for p in SYSTEM_EMAIL_PREFIXES)
        # 如果是來源展覽網站的 email 才過濾（例如 CustomerService@chanchao.com.tw）
        is_source = source_domain and source_domain in e
        if not is_system and not is_source:
            email = email_m.group(0)

    # 電話（台灣各種格式）
    phone_patterns = [
        r'\(?0[2-9]\d{0,2}\)?[-\s]?\d{3,4}[-\s]?\d{4}',       # (02)8979-6169、(07)-788-1114、02)8979-6169
        r'0[2-9]\d{0,2}[-\s\.]\d{3,4}[-\s\.]\d{4}',          # 02-8979-6169 或 02.8979.6169
        r'0[2-9]\d{0,2}[-\s\.]\d{6,8}',                       # 03-3792976 或 0800-007258（無中間分隔）
        r'09\d{2}[-\s]?\d{3}[-\s]?\d{3}',                     # 0912-345-678
        r'\+886[-\s]?[2-9]\d{0,1}[-\s]?\d{3,4}[-\s]?\d{4}',  # +886-2-1234-5678
        r'\+886\d{8,9}',                                        # +886286675469（無分隔符國際格式）
    ]
    for pattern in phone_patterns:
        m = re.search(pattern, text)
        if m:
            phone = re.sub(r'\s+', '', m.group(0))
            break

    return phone, email


# ── 展昭系列解析 ──────────────────────────────────────────────────────────────

def _is_chanchao_new(url: str) -> bool:
    """新版展昭 Nuxt.js（如 taiwanoutdoorshow-taichung.chanchao.com.tw/VisitorExhibitor）"""
    return 'chanchao.com.tw' in url and 'VisitorExhibitor' in url and '.asp' not in url

def _is_chanchao_old(url: str) -> bool:
    """舊版展昭 ASP（如 www.chanchao.com.tw/twsf/taichung/visitorExhibitor.asp）"""
    return 'chanchao.com.tw' in url and not _is_chanchao_new(url)


def _parse_chanchao_old_list(html: str, base_url: str) -> List[dict]:
    soup = BeautifulSoup(html, 'lxml')
    companies = {}
    for h4 in soup.select('h4 a[href*="visitorExhibitorDetail"]'):
        name = h4.get_text(strip=True)
        href = h4.get('href', '')
        if name and href:
            companies[name] = urllib.parse.urljoin(base_url, href)
    for a in soup.select('a[href*="visitorExhibitorDetail"][title]'):
        name = a.get('title', '').strip()
        href = a.get('href', '')
        if name and href and name not in companies:
            companies[name] = urllib.parse.urljoin(base_url, href)
    return [{'name': n, 'detail_url': u, 'website': '', 'phone': None, 'email': None}
            for n, u in companies.items()]


def _parse_chanchao_new_list(html: str, base_url: str) -> List[dict]:
    companies = {}
    for m in re.finditer(r'href=["\']([^"\']*Exhibitor[/\\]Detail\?regNo=(\d+))["\']', html):
        href, reg_no = m.group(1), m.group(2)
        if reg_no not in companies:
            companies[reg_no] = {'name': f'__pending__{reg_no}',
                                 'detail_url': urllib.parse.urljoin(base_url, href),
                                 'website': '', 'phone': None, 'email': None}
    for m in re.finditer(r'RegNo:(\d+),ComName:"([^"]+)"', html):
        reg_no, name = m.group(1), m.group(2)
        if reg_no in companies:
            companies[reg_no]['name'] = name
    return list(companies.values())


def _get_chanchao_new_total_pages(html: str) -> int:
    """從新版展昭 Nuxt 狀態取得總頁數"""
    m = re.search(r'totalPage:(\d+)', html)
    return int(m.group(1)) if m else 1


def _parse_chanchao_detail(html: str, base_url: str, is_new: bool = False) -> dict:
    """解析展昭廠商詳情頁"""
    soup = BeautifulSoup(html, 'lxml')
    result = {'phone': None, 'email': None, 'website': None, 'company_name': None}
    source_domain = get_domain(base_url)

    # 新版：公司名稱在 <title>
    if is_new:
        title = soup.find('title')
        if title:
            parts = title.get_text().split(' - ')
            if parts:
                result['company_name'] = parts[0].strip()

    # 移除頁首/頁尾
    for tag in soup.select('header, footer, nav, #menu, #menuWrapper, script, style'):
        tag.decompose()
    main = soup.select_one('#right, article, main, .content, #content') or soup
    text = main.get_text(separator=' ')

    phone, email = extract_contact_info(text, source_domain=source_domain)
    result['phone'] = phone
    result['email'] = email

    # 找官網（優先找標籤含關鍵字附近的連結）
    result['website'] = _find_website_in_content(soup, source_domain)
    return result


def _get_chanchao_next_pages(html: str, base_url: str, current_page: int) -> List[str]:
    soup = BeautifulSoup(html, 'lxml')
    pages = []
    page_div = soup.select_one('#page, .page, [id*="page"], [class*="pager"]')
    if not page_div:
        return []
    for a in page_div.select('a[href*="page="]'):
        m = re.search(r'page=(\d+)', a.get('href', ''))
        if m and int(m.group(1)) > current_page:
            pages.append(urllib.parse.urljoin(base_url, a.get('href', '')))
    return list(dict.fromkeys(pages))


# ── 通用解析輔助函數 ──────────────────────────────────────────────────────────

def _find_website_in_content(soup, source_domain: str) -> str:
    """在頁面中找公司官網連結（多策略）"""
    # 策略 A：「官網」等關鍵字附近的連結
    for el in soup.find_all(string=re.compile('|'.join(WEBSITE_KEYWORDS))):
        parent = el.find_parent(['p', 'div', 'li', 'td', 'span', 'a'])
        if not parent:
            continue
        for a in parent.select('a[href]'):
            w = normalize_url(a.get('href', ''))
            if is_company_website(w, source_domain):
                return w
        if parent.name == 'a':
            w = normalize_url(parent.get('href', ''))
            if is_company_website(w, source_domain):
                return w

    # 策略 B：main content 內的第一個外部連結
    main = soup.select_one('main, article, #content, #main, .content, .main, #right, .shop-info, .vendor-info')
    area = main if main else soup
    for a in area.select('a[href^="http"], a[href^="www."]'):
        w = normalize_url(a.get('href', ''))
        if is_company_website(w, source_domain):
            return w
    return ''


def _find_website_in_card(card, source_domain: str) -> str:
    """在卡片元素中找外部公司官網連結"""
    # 優先：class 含 link/url/web/site 的 a
    for a in card.select('a[class*="link"], a[class*="url"], a[class*="web"], a[class*="site"]'):
        w = normalize_url(a.get('href', ''))
        if is_company_website(w, source_domain):
            return w
    # 次要：target=_blank 的外部連結
    for a in card.select('a[target="_blank"][href]'):
        w = normalize_url(a.get('href', ''))
        if is_company_website(w, source_domain):
            return w
    # 備用：title 含 www 的連結
    for a in card.select('a[title]'):
        title = a.get('title', '')
        if 'www.' in title or title.startswith('http'):
            w = normalize_url(a.get('href', '') or title)
            if is_company_website(w, source_domain):
                return w
    return ''


# ── 通用列表頁解析 ────────────────────────────────────────────────────────────

_NOISE_WORDS = {
    # 英文導覽
    'more', 'read more', 'details', 'view', 'click', 'here', 'link',
    'home', 'back', 'next', 'previous', 'search', 'menu', 'close',
    'main area', '+ more', 'skip to main content',
    'login', 'sign in', 'sign up', 'register', 'logout', 'sign out',
    'my account', 'member', 'membership',
    # 中文導覽
    '更多', '查看', '詳細', '點擊', '了解更多', '詳情',
    '首頁', '回首頁', '回上頁', '展區', '展館', '樓層',
    '參觀者', '媒體', '參展廠商', '參展商', '國家', '地區',
    '參展商名稱', '品牌名稱', '參展商名稱a-z', '品牌名稱a-z',
    '聯絡我們', '關於我們', '新聞', '活動', '登入', '登出', '註冊',
    # 會員/票務相關（網站功能按鈕）
    '歡迎登入', '免費索票', '免費取票', '線上購票', '購票', '索票', '取票',
    '會員中心', '會員登入', '會員專區', '會員系統', '註冊會員', '我的帳戶',
    '持續更新中', '持續更新中~', '資料更新中', '陸續更新',
    '忘記密碼', '立即登入', '立即註冊', '重設密碼',
}

# 排除模式（regex）
_NOISE_PATTERNS = [
    re.compile(r'\(\d+\)'),              # "AI運算區(29)" — 含數量
    re.compile(r'^按\S'),                # "按Enter到..." — 無障礙提示
    re.compile(r'[A-Z]-[A-Z]'),          # "A-Z" 排序標籤
    re.compile(r'^\+\s'),                # "+ more"
    re.compile(r'[區館廳樓層]$'),        # 純展區名稱結尾
    re.compile(r'^\d+\s*$'),             # 純數字
    re.compile(r'^[\W\s]+$'),            # 純符號/空白
    re.compile(r'^[A-Z]{1,3}\d{3,4}$'), # 攤位號碼（K804、I628、AB1234）
    re.compile(r'^\d{4}[一-鿿]'),        # 年份開頭的中文標題（2025參展商列表）
    re.compile(r'更新中'),               # "持續更新中~"、"資料更新中"
    re.compile(r'(索票|取票|購票)'),     # 票務操作
    re.compile(r'^歡迎'),                # "歡迎登入"、"歡迎光臨"
    re.compile(r'^免費\S+(票|入場)'),    # "免費索票"、"免費入場"
    re.compile(r'(登入|登出|註冊|密碼)$'), # 以功能動詞結尾
    re.compile(r'^page\s*\d+$', re.IGNORECASE),   # 分頁連結 "page 2"、"page 3"
    re.compile(r'\b(terrace|pavilion|lounge|gallery|plaza|court)\s*$', re.IGNORECASE),  # 展覽區域名稱
    # 政府機關
    re.compile(r'管理局$'),                        # 科學園區管理局、工業區管理局
    re.compile(r'(科學園區|工業園區|加工出口區)'), # 科學/工業園區相關機構
    re.compile(r'^(衛生福利|教育|財政|經濟|國防|內政|外交|法務|勞動|農業|交通|文化|原住民族)(部|院)$'),  # 政府部會
    re.compile(r'^(行政院|立法院|司法院|考試院|監察院)'),  # 五院
    re.compile(r'國家.*委員會.*局'),               # 國家科學及技術委員會○部○局
]

# 詳情頁 URL 路徑關鍵字（判斷是否為廠商詳情連結）
_DETAIL_URL_HINTS = [
    'exhibitor', 'vendor', 'company', 'booth', 'brand', 'member',
    'participant', 'profile', 'detail', 'show', 'firm',
    '廠商', '參展', '品牌', '會員',
]


def _is_valid_brand_name(name: str) -> bool:
    """寬鬆版名稱過濾：長度 ≥ 2、不是純數字/符號、不是導覽/分類雜訊"""
    if not name or len(name) < 2:
        return False
    # 純數字/符號
    if re.fullmatch(r'[\d\s\W]+', name):
        return False
    # 黑名單關鍵字
    if name.lower().strip() in _NOISE_WORDS:
        return False
    # 雜訊模式
    for pat in _NOISE_PATTERNS:
        if pat.search(name):
            return False
    return True


def _is_detail_url(url: str) -> bool:
    """判斷 URL 是否像廠商詳情頁（含路徑關鍵字或數字 ID）"""
    url_lower = url.lower()
    for hint in _DETAIL_URL_HINTS:
        if hint in url_lower:
            return True
    # 路徑含數字 ID（如 /1234 或 /exhibitor/5678）
    if re.search(r'/\d{3,}', url_lower):
        return True
    return False


def _parse_generic_list(html: str, base_url: str, strict_name_filter: bool = True) -> List[dict]:
    """
    通用廠商列表解析 — 五種策略依序嘗試：
    1. 表格型     (table > tr > td)
    2. 標題連結型 (h2/h3/h4 > a)
    3. 卡片型     (div/li with class keywords)
    4. title 屬性 (a[title]) — 只收同網域連結
    5. 連結包文字 (a > p/span 等) — 只收有公司後綴的名稱
    每筆同時嘗試抓同容器內的電話/Email/官網（第一層命中就不需進詳情頁）

    strict_name_filter=False：接受所有品牌名稱（不強制要求公司後綴）
    """
    soup = BeautifulSoup(html, 'lxml')
    source_domain = get_domain(base_url)

    # 移除導覽雜訊
    for tag in soup.select('nav, header, footer, script, style, .nav, .footer, .menu, .sidebar, [class*="recommend"], [class*="related"]'):
        tag.decompose()

    results = {}

    def _same_domain_url(href: str) -> str:
        full = urllib.parse.urljoin(base_url, href)
        return full if source_domain in get_domain(full) else ''

    def _add(name: str, detail_url: str = '', phone=None, email=None, website: str = ''):
        name = name.strip()
        # 中英混合名稱取中文部分
        name = clean_company_name(name)
        # 名稱過濾：strict 模式要求公司後綴，寬鬆模式只排除雜訊
        if strict_name_filter:
            if not name or not is_company_name(name):
                return
        else:
            if not _is_valid_brand_name(name):
                return
        if name in results:
            # 補充缺少的欄位
            if website and not results[name].get('website'):
                results[name]['website'] = website
            if phone and not results[name].get('phone'):
                results[name]['phone'] = phone
            if email and not results[name].get('email'):
                results[name]['email'] = email
            return
        results[name] = {
            'name': name, 'detail_url': detail_url,
            'phone': phone, 'email': email,
            'website': website or '',
        }

    # ── 策略 1：表格型 ────────────────────────────────────────────────────────
    _BOOTH_PAT = re.compile(r'^[A-Z]{1,3}\d{3,4}$')
    for row in soup.select('table tr'):
        cells = row.select('td')
        if not cells:
            continue
        name_cell = cells[0]
        name = name_cell.get_text(strip=True)
        link = name_cell.select_one('a[href]')
        detail_url = _same_domain_url(link.get('href', '')) if link else ''
        # 若第一格是攤位號碼（K330 等），改用第二格當公司名稱
        if _BOOTH_PAT.match(name) and len(cells) > 1:
            name = cells[1].get_text(strip=True)
            # 第二格也可能有連結
            if not detail_url:
                link2 = cells[1].select_one('a[href]')
                if link2:
                    detail_url = _same_domain_url(link2.get('href', ''))
        row_text = row.get_text(separator=' ')
        phone, email = extract_contact_info(row_text, source_domain)
        website = _find_website_in_card(row, source_domain)
        _add(name, detail_url, phone, email, website)

    # ── 策略 2：標題連結型 ────────────────────────────────────────────────────
    for tag in soup.select('h1 a, h2 a, h3 a, h4 a, h5 a, h6 a'):
        name = tag.get_text(strip=True)
        detail_url = _same_domain_url(tag.get('href', ''))
        parent = tag.find_parent(['li', 'div', 'article', 'section', 'tr'])
        if parent:
            parent_text = parent.get_text(separator=' ')
            phone, email = extract_contact_info(parent_text, source_domain)
            website = _find_website_in_card(parent, source_domain)
        else:
            phone = email = website = None
        _add(name, detail_url, phone, email, website or '')

    # ── 策略 3：卡片/清單型 ───────────────────────────────────────────────────
    card_selectors = [
        '[class*="vendor"]',   '[class*="company"]',  '[class*="exhibitor"]',
        '[class*="member"]',   '[class*="brand"]',    '[class*="廠商"]',
        '[class*="item"]',     '[class*="card"]',     '[class*="list-row"]',
        '[class*="shop"]',
    ]
    for sel in card_selectors:
        for card in soup.select(sel):
            name_el = card.select_one(
                'h2, h3, h4, h5, strong, b, '
                '.name, [class*="name"], [class*="title"], '
                'a[class*="name"], a[class*="title"]'
            )
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            link = card.select_one('a[href]')
            detail_url = _same_domain_url(link.get('href', '')) if link else ''
            card_text = card.get_text(separator=' ')
            phone, email = extract_contact_info(card_text, source_domain)
            website = _find_website_in_card(card, source_domain)
            _add(name, detail_url, phone, email, website)

    # ── 策略 4：title 屬性型（展昭舊版 swiper 等）────────────────────────────
    for a in soup.select('a[title][href]'):
        name = a.get('title', '').strip()
        detail_url = _same_domain_url(a.get('href', ''))
        if detail_url:  # 只收同網域連結，避免社群分享按鈕
            _add(name, detail_url)

    # ── 策略 5：連結包文字型（tte.tw 等）─────────────────────────────────────
    # 觸發條件：前四策略都沒找到有 detail_url 的結果
    has_valid = any(v.get('detail_url') for v in results.values())
    if not has_valid:
        for a in soup.select('a[href]'):
            detail_url = _same_domain_url(a.get('href', ''))
            if not detail_url:
                continue
            inner_text = a.get_text(separator='', strip=True)
            if inner_text and is_company_name(inner_text):
                parent = a.find_parent(['li', 'div', 'tr', 'article'])
                phone = email = website = None
                if parent:
                    parent_text = parent.get_text(separator=' ')
                    phone, email = extract_contact_info(parent_text, source_domain)
                    website = _find_website_in_card(parent, source_domain)
                _add(inner_text, detail_url, phone, email, website or '')

    # ── 策略 6：寬鬆模式 — 詳情頁連結文字（品牌名稱、無後綴公司）────────────────
    # 只在 strict_name_filter=False 時啟用，且只跟「廠商詳情頁」URL（含關鍵字或數字 ID）
    if not strict_name_filter:
        for a in soup.select('a[href]'):
            detail_url = _same_domain_url(a.get('href', ''))
            if not detail_url or not _is_detail_url(detail_url):
                continue
            inner_text = a.get_text(separator='', strip=True)
            if not inner_text:
                continue
            parent = a.find_parent(['li', 'div', 'tr', 'article', 'section'])
            phone = email = website = None
            if parent:
                parent_text = parent.get_text(separator=' ')
                phone, email = extract_contact_info(parent_text, source_domain)
                website = _find_website_in_card(parent, source_domain)
            _add(inner_text, detail_url, phone, email, website or '')

    return list(results.values())


def _parse_generic_detail(html: str, base_url: str) -> dict:
    """通用詳情頁：抓電話、Email、官網"""
    soup = BeautifulSoup(html, 'lxml')
    source_domain = get_domain(base_url)

    for tag in soup.select('nav, header, footer, script, style, .nav, .footer, .menu, .sidebar, [class*="recommend"], [class*="related"]'):
        tag.decompose()

    text = soup.get_text(separator=' ')
    phone, email = extract_contact_info(text, source_domain)
    website = _find_website_in_content(soup, source_domain)

    return {'phone': phone, 'email': email, 'website': website}


def _get_next_page_generic(html: str, base_url: str) -> Optional[str]:
    """找下一頁連結"""
    soup = BeautifulSoup(html, 'lxml')
    for a in soup.select('a'):
        text = a.get_text(strip=True)
        if text in ('下一頁', '次頁', 'Next', '>', '›', '»', 'next'):
            href = a.get('href', '')
            if href and not href.startswith('#') and 'javascript' not in href.lower():
                return urllib.parse.urljoin(base_url, href)
    next_link = soup.select_one('a[rel="next"]')
    if next_link:
        return urllib.parse.urljoin(base_url, next_link.get('href', ''))
    return None


def _detect_dopage_pagination(html: str, base_url: str) -> Optional[dict]:
    """
    偵測 doPage(N) 型 JavaScript 分頁（如 taiwanhoreca.com.tw）。
    form action="" 表示提交到當前 URL，並附加 currentPage=N 參數。
    """
    pages = re.findall(r'doPage\((\d+)\)', html)
    if not pages:
        return None
    max_page = max(int(p) for p in pages)
    if max_page <= 1:
        return None

    # 找 pageForm 的 hidden inputs（額外附加參數）
    extra_params = {}
    for m in re.finditer(r'<input[^>]+name=["\'](\w+)["\'][^>]+value=["\']([^"\']*)["\']', html):
        name, value = m.group(1), m.group(2)
        if name not in ('condition', 'searchKey', 'applyId') and len(value) < 50:
            extra_params[name] = value

    # 用 currentPage=N 參數對當前 URL 分頁
    parsed = urllib.parse.urlparse(base_url)
    base_clean = urllib.parse.urlunparse(parsed._replace(query='', fragment=''))

    def _make_url(page_num: int) -> str:
        params = {**extra_params, 'currentPage': str(page_num)}
        return f"{base_clean}?{urllib.parse.urlencode(params)}"

    urls = [_make_url(p) for p in range(1, max_page + 1)]
    logger.info(f"doPage pagination: {max_page} pages, base={base_clean}")
    return {'type': 'dopage', 'urls': urls}


def _detect_ajax_pagination(html: str, base_url: str) -> Optional[dict]:
    """
    偵測 AJAX 分頁載入模式，回傳設定或 None。
    支援 jQuery $.ajax({url, data:{page, type}}) 等常見模式。
    策略：直接在全頁 HTML 中搜尋 data:{..., type:'xxx'} 取得 API 類型，
          再獨立找 ajax 呼叫中的 url 參數。
    """
    # ── 步驟 1：確認有 AJAX 分頁模式（包含 page 和某個 PHP/API 端點）──────────
    if not re.search(r'page\s*[,:]\s*page', html):
        return None  # 沒有動態 page 參數

    # ── 步驟 2：找 AJAX URL（.php 或 /api/ 路徑）────────────────────────────────
    ajax_url = None

    # 方法 A：jQuery ajax url 參數
    url_match = re.search(
        r'url\s*:\s*["\']([^"\']*(?:ajax|api|load|get)[^"\']*\.php[^"\']*)["\']',
        html, re.IGNORECASE
    )
    if url_match:
        ajax_url = urllib.parse.urljoin(base_url, url_match.group(1))

    # 方法 B：fetch/axios URL
    if not ajax_url:
        url_match2 = re.search(
            r'(?:fetch|axios\.(?:post|get))\s*\(\s*["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if url_match2:
            ajax_url = urllib.parse.urljoin(base_url, url_match2.group(1))

    if not ajax_url:
        return None

    # ── 步驟 3：從 data:{...} 中找 type 值（排除 HTTP method）─────────────────
    # 直接在全文搜尋 data:{ ... type:'xxx' ... }，不受巢狀括號影響
    data_type = None
    type_match = re.search(
        r'data\s*:\s*\{[^}]*?\btype\s*:\s*[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]',
        html
    )
    if type_match:
        val = type_match.group(1)
        if val.upper() not in ('POST', 'GET', 'PUT', 'DELETE', 'JSON', 'TEXT', 'HTML'):
            data_type = val

    logger.info(f"AJAX pagination detected: url={ajax_url}, type={data_type}")
    return {'url': ajax_url, 'type': data_type, 'method': 'POST'}


# ── Playwright 支援（JS 渲染 / Cloudflare 保護網站）─────────────────────────

def _needs_playwright(html: str) -> bool:
    """判斷頁面是否需要 Playwright（Cloudflare 攔截 或 JS 渲染框架）"""
    if not html or len(html) < 500:
        return True
    cf_markers = ['Just a moment', 'cf-browser-verification', 'cf_chl_opt',
                  'challenges.cloudflare.com', 'Enable JavaScript and cookies']
    if any(m in html for m in cf_markers):
        return True
    js_markers = ['__NEXT_DATA__', 'window.__nuxt__', 'id="__vue"',
                  'data-reactroot', 'ng-version=', 'data-svelte']
    # Shopline / Liquid 模板語法（客戶端渲染，電話/Email 在 JS 執行後才出現）
    if 'cdn.shoplineapp.com' in html or '| translate }}' in html or "| t }}" in html:
        return True
    # JS 框架但內容很少（空 div，典型 CSR）
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    text_content = soup.get_text(strip=True)
    if any(m in html for m in js_markers) and len(text_content) < 200:
        return True
    return False


async def _fetch_with_playwright(url: str, wait_for: str = 'networkidle') -> str:
    """用 Playwright Chromium 取得完整渲染後的 HTML"""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox',
                      '--disable-dev-shm-usage', '--disable-gpu',
                      '--ignore-certificate-errors']
            )
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                locale='zh-TW',
                viewport={'width': 1280, 'height': 800},
                ignore_https_errors=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.7,en;q=0.6',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                },
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until=wait_for, timeout=8000)
            await page.wait_for_timeout(800)
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        logger.warning(f"Playwright fetch error ({url}): {e}")
        return ''


# ── 第三層：進官網抓電話/Email ────────────────────────────────────────────────

async def _scrape_company_website(client: httpx.AsyncClient, website: str) -> Tuple[Optional[str], Optional[str]]:
    """
    進入公司官網（及聯絡/關於頁），抓電話和 Email。
    公司自己 domain 的 email 是我們要的，不過濾。
    只過濾系統無效信箱 (noreply 等)。
    """
    phone, email = None, None
    website_domain = get_domain(website)

    async def _extract_from_html(html: str) -> None:
        """從 HTML 中抽取電話和 Email"""
        nonlocal phone, email
        soup = BeautifulSoup(html, 'lxml')
        for tag in soup.select('script, style, nav, header'):
            tag.decompose()
        text = soup.get_text(separator=' ')
        p, e = extract_contact_info(text, source_domain='')
        # 若電話未找到，用無分隔符版本再試（處理電話數字被拆成多個 HTML 元素的情況）
        if not p:
            compact = soup.get_text(separator='')
            p, _ = extract_contact_info(compact, source_domain='')
        if p and not phone:
            phone = p
        if e and not email:
            email = e

    async def _fetch_and_extract(target_url: str) -> str:
        """用 HTTP 抓頁面，若偵測到 Cloudflare/JS 渲染則切換 Playwright，回傳 HTML"""
        nonlocal phone, email
        html = ''
        skip_playwright = False
        try:
            await asyncio.sleep(0.2)
            r = await client.get(target_url, timeout=12)
            r.raise_for_status()
            html = r.text
        except httpx.HTTPStatusError as ex:
            # 4xx 表示網站拒絕存取，Playwright 通常也無法繞過（404 一定無用）
            if ex.response.status_code == 404:
                skip_playwright = True
            logger.debug(f"  HTTP {ex.response.status_code}: {target_url}")
        except Exception as ex:
            logger.debug(f"  HTTP fetch error {target_url}: {ex}")
            # SSL 憑證錯誤：改用 verify=False 重試
            try:
                async with httpx.AsyncClient(
                    headers=HEADERS, verify=False, timeout=12, follow_redirects=True
                ) as nc:
                    r2 = await nc.get(target_url, timeout=12)
                    r2.raise_for_status()
                    html = r2.text
                    skip_playwright = True  # 已取得內容，不需再用 Playwright
            except Exception:
                pass

        # 先從 httpx HTML 提取（靜態頁面直接完成）
        if html:
            await _extract_from_html(html)

        # Playwright 補充：頁面需要 JS 渲染 且 資料還不完整
        if not skip_playwright and _needs_playwright(html) and not (phone and email):
            logger.info(f"  Playwright fallback: {target_url}")
            playwright_html = await _fetch_with_playwright(target_url)
            if playwright_html:  # 只在成功時覆蓋，避免超時後丟失 httpx 結果
                await _extract_from_html(playwright_html)
                html = playwright_html

        return html

    # 1. 抓首頁
    homepage_html = await _fetch_and_extract(website)

    # 2. 若還缺資料，找聯絡/關於頁
    if not phone or not email:
        try:
            soup0 = BeautifulSoup(homepage_html, 'lxml') if homepage_html else None
            if soup0:
                visited_contact = set()
                for a in soup0.select('a[href]'):
                    href = a.get('href', '')
                    link_text = a.get_text(strip=True).lower()
                    href_lower = href.lower()
                    is_contact = any(h in href_lower or h in link_text for h in CONTACT_PAGE_HINTS)
                    if is_contact:
                        contact_url = urllib.parse.urljoin(website, href)
                        if get_domain(contact_url) == website_domain and contact_url not in visited_contact:
                            visited_contact.add(contact_url)
                            await _fetch_and_extract(contact_url)
                            if phone and email:
                                break
        except Exception:
            pass

    return phone, email


# ── 主爬蟲 ────────────────────────────────────────────────────────────────────

async def scrape(url: str, keyword: str = None, industry: str = None, limit: int = 50, strict_name_filter: bool = False, **kwargs) -> List[dict]:
    """
    三層通用爬蟲：列表頁 → 詳情頁 → 官網
    自動偵測展昭新/舊版、通用頁面。

    strict_name_filter=False：接受品牌名稱（不強制公司後綴），適合展覽/品牌目錄網站。
    """
    lim = min(limit or 50, 300)
    is_chanchao_new = _is_chanchao_new(url)
    is_chanchao_old = _is_chanchao_old(url)

    all_items: List[dict] = []
    visited = set()
    current_url = url
    current_page = 1

    async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:

        # ── 第一層：爬所有列表頁 ──────────────────────────────────────────────
        ajax_config = None
        dopage_config = None
        chanchao_new_total_pages = 1  # 在迴圈外宣告，才能跨頁保持

        while current_url and current_url not in visited and len(all_items) < lim:
            visited.add(current_url)
            try:
                await asyncio.sleep(0.8)
                resp = await client.get(current_url)
                resp.raise_for_status()
                html = resp.text
            except Exception as e:
                logger.warning(f"List page fetch error ({current_url}): {e}")
                break

            if is_chanchao_new:
                items = _parse_chanchao_new_list(html, url)
            elif is_chanchao_old:
                items = _parse_chanchao_old_list(html, url)
            else:
                items = _parse_generic_list(html, url, strict_name_filter=strict_name_filter)

            # keyword 篩選
            if keyword:
                kw = keyword.lower()
                filtered = [i for i in items if kw in i['name'].lower()]
                items = filtered if filtered else items

            all_items.extend(items)
            logger.info(f"Page {current_page}: {len(items)} items, total {len(all_items)}")

            # 偵測分頁模式（只在第一頁偵測一次）
            if current_page == 1:
                if is_chanchao_new:
                    chanchao_new_total_pages = _get_chanchao_new_total_pages(html)
                    logger.info(f"chanchao_new: {chanchao_new_total_pages} total pages")
                elif not is_chanchao_old:
                    dopage_config = _detect_dopage_pagination(html, url)
                    if not dopage_config:
                        ajax_config = _detect_ajax_pagination(html, url)
                        if ajax_config:
                            logger.info(f"AJAX pagination detected: {ajax_config['url']}")

            # 找下一頁
            if is_chanchao_new and current_page < chanchao_new_total_pages:
                # 新版展昭：用 ?page=N 翻頁
                base_no_query = url.split('?')[0]
                current_url = f"{base_no_query}?page={current_page + 1}"
            elif is_chanchao_old:
                next_pages = _get_chanchao_next_pages(html, url, current_page)
                current_url = next_pages[0] if next_pages else None
            elif dopage_config or ajax_config:
                current_url = None  # 由下面的迴圈處理
            else:
                current_url = _get_next_page_generic(html, url)
            current_page += 1
            if current_page > 100:  # 安全上限
                break

        # ── doPage 分頁翻頁（如 taiwanhoreca.com.tw）────────────────────────
        if dopage_config and len(all_items) < lim:
            page_urls = dopage_config['urls'][1:]  # 第1頁已在 while 迴圈抓過，從第2頁開始
            for page_url in page_urls:
                if len(all_items) >= lim:
                    break
                try:
                    await asyncio.sleep(0.8)
                    resp = await client.get(page_url, headers={**HEADERS, 'Referer': url})
                    resp.raise_for_status()
                    page_html = resp.text
                    items = _parse_generic_list(page_html, url, strict_name_filter=strict_name_filter)
                    if keyword:
                        kw = keyword.lower()
                        filtered = [i for i in items if kw in i['name'].lower()]
                        items = filtered if filtered else items
                    all_items.extend(items)
                    logger.info(f"doPage: {page_url} → {len(items)} items, total {len(all_items)}")
                except Exception as e:
                    logger.warning(f"doPage fetch error {page_url}: {e}")

        # ── AJAX 分頁翻頁（如 tibe.org.tw）─────────────────────────────────
        if ajax_config and len(all_items) < lim:
            ajax_url = ajax_config['url']
            ajax_type = ajax_config.get('type', '')
            ajax_page = 1
            consecutive_empty = 0

            while len(all_items) < lim and consecutive_empty < 3:
                try:
                    await asyncio.sleep(0.8)
                    post_data = {'page': str(ajax_page)}
                    if ajax_type:
                        post_data['type'] = ajax_type
                    resp = await client.post(
                        ajax_url,
                        data=post_data,
                        headers={**HEADERS, 'Referer': url,
                                 'Content-Type': 'application/x-www-form-urlencoded'},
                    )
                    resp.raise_for_status()
                    ajax_html = resp.text

                    # 解析 AJAX 回傳的 HTML 片段
                    items = _parse_generic_list(ajax_html, url, strict_name_filter=strict_name_filter)
                    if keyword:
                        kw = keyword.lower()
                        filtered = [i for i in items if kw in i['name'].lower()]
                        items = filtered if filtered else items

                    if not items:
                        consecutive_empty += 1
                    else:
                        consecutive_empty = 0
                        all_items.extend(items)
                        logger.info(f"AJAX page {ajax_page}: {len(items)} items, total {len(all_items)}")

                    ajax_page += 1
                    if ajax_page > 100:  # 安全上限
                        break
                except Exception as e:
                    logger.warning(f"AJAX page {ajax_page} error: {e}")
                    break

        # 去重（以公司名稱為 key，後出現的補充缺少的欄位）
        seen = {}  # name -> item
        for item in all_items:
            name = item['name']
            # __pending__ 項目：用 detail_url 當 key 去重（新版展昭公司名稱待詳情頁補充）
            key = item.get('detail_url') if name.startswith('__pending__') else name
            if not key:
                continue
            if key not in seen:
                seen[key] = item
            else:
                existing = seen[key]
                for field in ('website', 'phone', 'email', 'detail_url'):
                    if item.get(field) and not existing.get(field):
                        existing[field] = item[field]
        unique_items = list(seen.values())[:lim]

        logger.info(f"Total unique: {len(unique_items)} companies")

        # ── 第二層：詳情頁（只有缺資料時才進）──────────────────────────────────
        results = []
        website_scrape_count = 0  # 第三層最多補 100 家
        for item in unique_items:
            phone   = item.get('phone')
            email   = item.get('email')
            website = item.get('website') or None
            detail  = {}

            # 只在缺少資料時才進詳情頁
            need_detail = (not phone or not email or not website) and item.get('detail_url')
            if need_detail and item['detail_url'] not in visited:
                try:
                    await asyncio.sleep(0.5)
                    r = await client.get(item['detail_url'])
                    r.raise_for_status()
                    if is_chanchao_new:
                        detail = _parse_chanchao_detail(r.text, url, is_new=True)
                    elif is_chanchao_old:
                        detail = _parse_chanchao_detail(r.text, url, is_new=False)
                    else:
                        detail = _parse_generic_detail(r.text, url)
                    visited.add(item['detail_url'])
                    if not phone:
                        phone = detail.get('phone')
                    if not email:
                        email = detail.get('email')
                    if not website:
                        website = detail.get('website')
                except Exception as e:
                    logger.warning(f"Detail page error {item['detail_url']}: {e}")

            # ── 第三層：官網（有官網但還缺電話/Email，且未超過上限）──────────────
            if website and (not phone or not email) and website_scrape_count < 100:
                website_scrape_count += 1
                phone_w, email_w = await _scrape_company_website(client, website)
                if phone_w and not phone:
                    phone = phone_w
                if email_w and not email:
                    email = email_w

            # 新版展昭：公司名稱補充
            company_name = item['name']
            if company_name.startswith('__pending__') and detail.get('company_name'):
                company_name = detail['company_name']
            elif company_name.startswith('__pending__'):
                company_name = '廠商 #' + company_name.replace('__pending__', '')

            results.append({
                'company_name': company_name,
                'contact_name': None,
                'title': None,
                'email': email,
                'phone': phone,
                'website': website,
                'industry': industry or '展覽廠商',
                'city': None,
                'company_size': None,
                'source': 'custom_url',
                'source_url': url,
                'notes': None,
            })

    logger.info(f"Scrape done: {len(results)} results from {url}")
    return results
