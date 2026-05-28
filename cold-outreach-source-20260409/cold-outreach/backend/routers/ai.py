import os
import json
import re
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import google.generativeai as genai
from database import get_db
from models import User, Lead, LeadActivity, LeadStatus, ActivityType
from schemas import DraftRequest, DraftResponse
from auth import get_current_user
from utils import now_tw

router = APIRouter(prefix="/api/ai", tags=["ai"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

TEMPLATES = {
    "intro": "初次開發信。這是第一次接觸，請保持專業但友善，簡要介紹我們的數位行銷服務，並提出一個明確的行動呼籲（安排 15 分鐘通話）。",
    "followup": "追蹤跟進信。我們之前已有接觸但尚未回應，請溫和提醒，不要施壓，強調我們能提供的具體價值。",
    "proposal": "報價提案信。針對客戶需求提出具體方案，包含服務項目概述、預期效益，並邀請進一步討論細節。",
}


@router.post("/draft", response_model=DraftResponse)
def generate_draft(
    body: DraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API key not configured")

    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    template_hint = TEMPLATES.get(body.template_type, TEMPLATES["intro"])

    background_section = ""
    if body.customer_background and body.customer_background.strip():
        background_section = f"""
客戶官網／背景資訊（請仔細閱讀並融入信件，讓內容更貼近客戶實際情況）：
---
{body.customer_background.strip()[:3000]}
---
"""

    prompt = f"""你是一位專業的數位行銷業務，正在撰寫開發信。

目標客戶資訊：
- 公司名稱：{lead.company_name}
- 聯絡人：{lead.contact_name or "（未知）"}
- 職稱：{lead.title or "（未知）"}
- 產業：{lead.industry or "數位行銷"}
- 城市：{lead.city or "台灣"}
- 官網：{lead.website or "（未知）"}
{background_section}
信件類型：{body.template_type}
指導方針：{template_hint}

請用繁體中文撰寫一封專業的開發信。若有提供客戶背景資訊，請具體提及客戶的產品/服務，讓信件更有針對性，而非泛泛而談。
回應格式（嚴格遵守）：
SUBJECT: <信件主旨>
BODY:
<信件內文>

不要加任何其他說明。"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")

    # Parse subject + body
    subject = ""
    body_text = ""
    if "SUBJECT:" in text and "BODY:" in text:
        parts = text.split("BODY:", 1)
        subject_line = parts[0].replace("SUBJECT:", "").strip()
        subject = subject_line
        body_text = parts[1].strip()
    else:
        lines = text.split("\n")
        subject = lines[0]
        body_text = "\n".join(lines[1:]).strip()

    return DraftResponse(subject=subject, body=body_text)


# ── AI Enrich ─────────────────────────────────────────────────────────────────

class EnrichRequest(BaseModel):
    company_name: str
    lead_id: str


import re as _re
from urllib.parse import urljoin as _urljoin

_EMAIL_RE = _re.compile(r'[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}')

# Taiwan phone: landline (02) 2345-6789, 03-456-7890, mobile 0912-345-678, +886 prefix
_PHONE_RE = _re.compile(
    r'(?:'
    r'\(?0[2-8]\)?[-\s\.]{0,2}\d{3,4}[-\s\.]{0,2}\d{4}'   # landline: (02) or 02-
    r'|\(?09\d{2}\)?[-\s\.]{0,2}\d{3}[-\s\.]{0,2}\d{3}'   # mobile: (09xx) or 09xx-
    r'|\+886[-\s\.]{0,2}[2-9][-\s\.]{0,2}\d{3,4}[-\s\.]{0,2}\d{4}'  # +886
    r')'
)

# Keywords that indicate a contact page (order matters for scoring)
_CONTACT_KWS = [
    "聯絡我們", "contact-us", "contactus", "contact_us",
    "聯絡", "連絡", "contact",
    "reach", "get-in-touch", "connect",
    "about", "關於",
]

# Fallback paths to probe when no contact link found in page HTML
_CONTACT_PATHS = [
    "/contact", "/contact-us", "/contactus", "/contact_us",
    "/about/contact", "/about-us", "/about",
    "/pages/contact", "/pages/contact-us",
    "/zh/contact", "/tw/contact",
    "/get-in-touch", "/support",
    "/company/contact",
]

_SKIP_EMAIL_PARTS = ["example", "test", "noreply", "no-reply", "donotreply",
                     ".png", ".jpg", ".gif", ".svg", ".css", ".js", "sentry",
                     "wixpress", "w3school", "schema.org"]

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}


def _strip_tags(html: str) -> str:
    text = _re.sub(r'<[^>]+>', ' ', html)
    return _re.sub(r'\s+', ' ', text).strip()


def _find_emails(text: str) -> list[str]:
    # Also handle basic obfuscation like [at] / (at)
    normalized = (
        text
        .replace(" [at] ", "@").replace(" (at) ", "@")
        .replace("[at]", "@").replace("(at)", "@")
        .replace(" [dot] ", ".").replace(" (dot) ", ".")
        .replace("[dot]", ".").replace("(dot)", ".")
    )
    found = _EMAIL_RE.findall(normalized)
    result = []
    seen: set[str] = set()
    for e in found:
        el = e.lower()
        if el in seen:
            continue
        if any(skip in el for skip in _SKIP_EMAIL_PARTS):
            continue
        seen.add(el)
        result.append(e)
    return result


def _find_phones(text: str) -> list[str]:
    found = _PHONE_RE.findall(text)
    cleaned = []
    seen: set[str] = set()
    for p in found:
        # Normalise to digits only for dedup
        c = _re.sub(r'[\s\-\.\(\)]', '', p)
        if c not in seen and len(c) >= 8:
            seen.add(c)
            cleaned.append(p.strip())
    return cleaned


def _extract_jsonld_contacts(html: str) -> dict:
    """Extract email / phone from JSON-LD structured data embedded in <script> tags."""
    schema_re = _re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        _re.DOTALL | _re.IGNORECASE,
    )
    emails: list[str] = []
    phones: list[str] = []
    for match in schema_re.findall(html):
        try:
            data = json.loads(match.strip())
            # JSON-LD may be a list
            items = data if isinstance(data, list) else [data]
            for item in items:
                for key in ("email", "Email"):
                    val = item.get(key)
                    if val and isinstance(val, str):
                        emails.append(val)
                for key in ("telephone", "Telephone", "phone", "Phone"):
                    val = item.get(key)
                    if val and isinstance(val, str):
                        phones.append(val)
                # contactPoint
                cp = item.get("contactPoint") or []
                if isinstance(cp, dict):
                    cp = [cp]
                for point in cp:
                    if point.get("email"):
                        emails.append(point["email"])
                    if point.get("telephone"):
                        phones.append(point["telephone"])
        except Exception:
            pass
    # Deduplicate while preserving order
    seen_e: set[str] = set()
    seen_p: set[str] = set()
    emails = [e for e in emails if not (e.lower() in seen_e or seen_e.add(e.lower()))]  # type: ignore[func-returns-value]
    phones = [p for p in phones if not (_re.sub(r'[^\d]', '', p) in seen_p or seen_p.add(_re.sub(r'[^\d]', '', p)))]  # type: ignore[func-returns-value]
    return {"emails": emails, "phones": phones}


async def _scrape_contact_info(website: str) -> dict:
    """
    Given a company website URL:
    1. Fetch homepage and extract JSON-LD structured data
    2. Discover the "Contact Us" page via scored link matching + fallback paths
    3. Fetch the contact page and extract JSON-LD / regex email+phone
    4. Fall back to Gemini if regex finds nothing
    Returns dict with keys: email, phone, contact_url
    """
    base = website if website.startswith("http") else f"https://{website}"

    try:
        async with httpx.AsyncClient(
            timeout=15, headers=_HTTP_HEADERS, follow_redirects=True
        ) as client:
            # ── Step 1: Fetch homepage ──────────────────────────────────────
            try:
                res = await client.get(base)
                main_html = res.text
            except Exception:
                return {}

            # ── Step 2: Try JSON-LD on homepage first ─────────────────────
            jsonld = _extract_jsonld_contacts(main_html)
            if jsonld["emails"] or jsonld["phones"]:
                return {
                    "email": jsonld["emails"][0] if jsonld["emails"] else None,
                    "phone": jsonld["phones"][0] if jsonld["phones"] else None,
                    "contact_url": None,
                }

            # ── Step 3: Scored link search for contact page ───────────────
            link_re = _re.compile(r'href=["\']([^"\'\s#][^"\']*)["\']', _re.IGNORECASE)
            all_links = link_re.findall(main_html)

            contact_url: str | None = None
            best_score = 0
            for href in all_links:
                href_lower = href.lower()
                # Skip anchors, mailto, tel, external social
                if href_lower.startswith(("mailto:", "tel:", "javascript:")):
                    continue
                score = 0
                for i, kw in enumerate(_CONTACT_KWS):
                    if kw.lower() in href_lower:
                        # Earlier keywords in the list get higher priority
                        score += max(5 - i, 1)
                if score > best_score:
                    best_score = score
                    contact_url = _urljoin(base, href)

            # ── Step 4: Fallback paths when no link discovered ────────────
            if not contact_url:
                for suffix in _CONTACT_PATHS:
                    try:
                        r = await client.get(_urljoin(base, suffix), timeout=8)
                        if r.status_code == 200 and len(r.text) > 200:
                            contact_url = _urljoin(base, suffix)
                            break
                    except Exception:
                        pass

            # ── Step 5: Fetch contact page ─────────────────────────────────
            target_html = main_html
            if contact_url:
                try:
                    r = await client.get(contact_url, timeout=10)
                    if r.status_code == 200:
                        target_html = r.text
                        # Try JSON-LD on contact page
                        jsonld = _extract_jsonld_contacts(r.text)
                        if jsonld["emails"] or jsonld["phones"]:
                            return {
                                "email": jsonld["emails"][0] if jsonld["emails"] else None,
                                "phone": jsonld["phones"][0] if jsonld["phones"] else None,
                                "contact_url": contact_url,
                            }
                except Exception:
                    pass

            # ── Step 6: Regex extraction ───────────────────────────────────
            text = _strip_tags(target_html)
            emails = _find_emails(text)
            phones = _find_phones(text)

            # ── Step 7: Gemini fallback if regex finds nothing ─────────────
            if not emails and not phones and GEMINI_API_KEY:
                snippet = text[:4000]
                prompt = f"""以下是一個公司聯絡頁面的文字內容，請仔細尋找 Email 地址和電話號碼（包含台灣常見格式如 (02)2345-6789 或 0912-345-678）。
只回傳 JSON，格式如下（沒有則填 null）：
{{"email": "第一個有效 email", "phone": "第一個有效電話"}}

內容：
{snippet}"""
                try:
                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    resp = model.generate_content(prompt)
                    raw = resp.text.strip()
                    raw = _re.sub(r'^```json\s*', '', raw)
                    raw = _re.sub(r'^```\s*', '', raw)
                    raw = _re.sub(r'\s*```$', '', raw)
                    parsed = json.loads(raw.strip())
                    if parsed.get("email"):
                        emails = [parsed["email"]]
                    if parsed.get("phone"):
                        phones = [parsed["phone"]]
                except Exception:
                    pass

            return {
                "email": emails[0] if emails else None,
                "phone": phones[0] if phones else None,
                "contact_url": contact_url,
            }
    except Exception:
        return {}


@router.post("/enrich")
async def enrich_company(
    body: EnrichRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Use Gemini to enrich company info (industry, city, company_size, email, phone)."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API key not configured")

    prompt = f"""請根據公司名稱「{body.company_name}」，推測並補全以下資訊（繁體中文，JSON格式回傳）：

{{
  "industry": "產業類別（例如：科技/製造/零售/金融/餐飲/教育等）",
  "city": "總部城市（台灣城市名稱）",
  "company_size": "公司規模（例如：1-10人/11-50人/51-200人/201-500人/500人以上）",
  "website": "公司官方網站完整網址（若能確定請填，否則填 null）",
  "summary": "公司簡介（50字以內）"
}}

只回傳JSON，不要任何說明。"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI 回傳格式錯誤")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")

    # Auto-update the lead (basic fields — only fill empty)
    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if lead:
        if data.get("industry") and not lead.industry:
            lead.industry = data["industry"]
        if data.get("city") and not lead.city:
            lead.city = data["city"]
        if data.get("company_size") and not lead.company_size:
            lead.company_size = data["company_size"]

        # ── Use AI-suggested website if lead has none ──────────────────────
        ai_website = data.get("website")
        if ai_website and not lead.website:
            # Basic sanity check before saving
            if isinstance(ai_website, str) and "." in ai_website:
                if not ai_website.startswith("http"):
                    ai_website = f"https://{ai_website}"
                lead.website = ai_website
                data["ai_suggested_website"] = ai_website

        # ── Scrape contact page for email / phone ──────────────────────────
        website_to_scrape = lead.website
        contact_info: dict = {}
        if website_to_scrape:
            contact_info = await _scrape_contact_info(website_to_scrape)
            scraped_email = contact_info.get("email")
            scraped_phone = contact_info.get("phone")
            if scraped_email and not lead.email:
                lead.email = scraped_email
                data["scraped_email"] = scraped_email
            if scraped_phone and not lead.phone:
                lead.phone = scraped_phone
                data["scraped_phone"] = scraped_phone
            data["contact_url"] = contact_info.get("contact_url")
        else:
            data["scraped_email"] = None
            data["scraped_phone"] = None
            data["contact_url"] = None

        db.commit()

    return data


# ── Pipeline Health ───────────────────────────────────────────────────────────

@router.post("/pipeline_health")
def pipeline_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze overall pipeline and return Markdown health report."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API key not configured")

    from sqlalchemy import func

    total = db.query(Lead).count()
    by_status = {}
    for row in db.query(Lead.status, func.count()).group_by(Lead.status).all():
        by_status[row[0].value] = row[1]

    week_ago = now_tw() - timedelta(days=7)
    emails_week = db.query(LeadActivity).filter(
        LeadActivity.type == ActivityType.email_sent,
        LeadActivity.created_at >= week_ago,
    ).count()

    stale_threshold = now_tw() - timedelta(days=7)
    stale_count = 0
    for lead in db.query(Lead).filter(Lead.status.in_([LeadStatus.contacted, LeadStatus.replied])).all():
        last = db.query(LeadActivity).filter(
            LeadActivity.lead_id == lead.id
        ).order_by(LeadActivity.created_at.desc()).first()
        if not last or last.created_at < stale_threshold:
            stale_count += 1

    prompt = f"""你是一位資深 B2B 業務顧問。請根據以下 Pipeline 數據，生成一份繁體中文的 Markdown 健診報告：

## Pipeline 數據
- 總名單數：{total}
- 各狀態分佈：{json.dumps(by_status, ensure_ascii=False)}
- 本週發信數：{emails_week}
- 超過7天未跟進：{stale_count} 筆

## 報告要求
請用 Markdown 格式，包含：
1. **健康度評分**（0-100分 + 評語）
2. **關鍵風險**（條列）
3. **建議行動**（優先順序排列）
4. **本週重點任務**（3項）

保持專業、具體、可執行。字數約 300-500 字。"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return {"report": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")


# ── Gmail Reply Detection ─────────────────────────────────────────────────────

@router.post("/gmail/check_replies")
def check_gmail_replies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check Gmail inbox for replies and auto-update lead status."""
    if not current_user.gmail_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    import base64
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_data = json.loads(current_user.gmail_token)
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    try:
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(
            userId="me", q="in:inbox is:unread", maxResults=50
        ).execute()
        messages = results.get("messages", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail error: {str(e)}")

    # Get all sent email addresses from leads
    leads = db.query(Lead).filter(
        Lead.assigned_to == current_user.id,
        Lead.email.isnot(None),
        Lead.status.in_([LeadStatus.contacted]),
    ).all()
    lead_emails = {l.email.lower(): l for l in leads if l.email}

    updated = []
    for msg in messages:
        try:
            full_msg = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()
            headers = {h["name"]: h["value"] for h in full_msg.get("payload", {}).get("headers", [])}
            from_email = headers.get("From", "").lower()

            # Check if sender matches any lead email
            for email, lead in lead_emails.items():
                if email in from_email:
                    if lead.status == LeadStatus.contacted:
                        lead.status = LeadStatus.replied
                        activity = LeadActivity(
                            lead_id=lead.id,
                            type=ActivityType.status_change,
                            content=f"Gmail 自動偵測回信 → 狀態更新為「已回覆」\nSubject: {headers.get('Subject', '')}",
                            created_by=current_user.id,
                        )
                        db.add(activity)
                        updated.append(lead.company_name)
                        break
        except Exception:
            continue

    if updated:
        db.commit()

    return {"updated_leads": updated, "checked_messages": len(messages)}


# ── AI 客製化 Email（輸入官網生成） ───────────────────────────────────────────

class GenerateEmailRequest(BaseModel):
    website_url: str
    product: str
    lead_id: Optional[str] = None
    tone: str = "professional"  # professional / friendly / urgent


PRODUCT_DESCRIPTIONS = {
    "SEO優化": "透過技術SEO、內容優化與外部連結建立，提升網站搜尋排名，增加自然流量",
    "廣告投放": "專業管理Google/Meta/LINE等數位廣告，精準觸達目標受眾，最大化廣告投資報酬率",
    "社群代操": "代管Facebook、Instagram、LINE官帳號等社群媒體，建立品牌形象與粉絲互動",
    "整合行銷": "跨平台整合行銷策略，結合SEO、社群、廣告、EDM等多管道協同運作",
    "KOL行銷": "媒合適合品牌的網紅KOL，執行口碑行銷活動，擴大品牌聲量與轉換",
}

TONE_DESCRIPTIONS = {
    "professional": "專業正式，商務語氣，展現專業能力",
    "friendly": "親切友善，拉近距離，自然對話風格",
    "urgent": "製造急迫感，限時優惠或市場競爭壓力",
}

_STRIP_TAGS_RE = re.compile(r'<[^>]+>')


def strip_html_tags(html: str) -> str:
    text = _STRIP_TAGS_RE.sub(' ', html)
    return re.sub(r'\s+', ' ', text).strip()


@router.post("/generate-email")
async def generate_email(
    body: GenerateEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a customized email using the client's website content."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API key not configured")

    # 1. Fetch website
    website_summary = ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        }
        async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
            res = await client.get(body.website_url)
            raw_html = res.text[:8000]
            website_summary = strip_html_tags(raw_html)[:3000]
    except Exception as e:
        website_summary = f"（無法讀取官網：{str(e)[:100]}）"

    product_desc = PRODUCT_DESCRIPTIONS.get(body.product, body.product)
    tone_desc = TONE_DESCRIPTIONS.get(body.tone, body.tone)

    prompt = f"""你是潮網科技的業務，正在撰寫一封客製化開發信。

【客戶官網內容摘要】
{website_summary[:2000]}

【潮網主推服務】
服務名稱：{body.product}
服務說明：{product_desc}

【語氣要求】
{tone_desc}

請根據以上資訊，用繁體中文撰寫一封 200 字以內的開發信。
信件必須：
1. 提及客戶的業務特色（從官網摘要中找出1-2個具體亮點）
2. 說明潮網如何幫助客戶成長
3. 提出明確的下一步（如：安排 15 分鐘線上會議）
4. 語氣符合要求

回應格式（嚴格遵守）：
SUBJECT: <信件主旨>
BODY:
<信件內文>

不要加任何其他說明。"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")

    # Parse subject + body
    subject = ""
    body_text = ""
    if "SUBJECT:" in text and "BODY:" in text:
        parts = text.split("BODY:", 1)
        subject = parts[0].replace("SUBJECT:", "").strip()
        body_text = parts[1].strip()
    else:
        lines = text.split("\n")
        subject = lines[0]
        body_text = "\n".join(lines[1:]).strip()

    return {
        "subject": subject,
        "body": body_text,
        "website_summary": website_summary[:500],
    }


# ── 提案信生成 ─────────────────────────────────────────────────────────────────

class GenerateProposalRequest(BaseModel):
    lead_id: str
    product: str  # 主推產品
    tone: str = "professional"
    include_benchmark: bool = True  # 是否包含產業 benchmark


@router.post("/generate-proposal")
async def generate_proposal(
    body: GenerateProposalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    生成完整提案信：
    1. 抓取 lead 的含金量分析結果（tech/ad signals）
    2. 用 Gemini 生成包含客戶現況分析 + 潮網服務建議的提案信
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API key not configured")

    lead = db.query(Lead).filter(Lead.id == body.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 整理客戶資訊
    tech = lead.tech_signals or {}
    ad = lead.ad_signals or {}
    score = lead.enriched_score or 0

    # 分析現況
    has_gtm = tech.get("gtm", False)
    has_pixel = tech.get("meta_pixel", False)
    has_ga4 = tech.get("ga4", False)
    has_meta_ads = ad.get("meta", {}).get("has_ads", False)
    has_google_ads = ad.get("google_ads", {}).get("has_ads", False)

    # 潮網產品對應說明
    PRODUCTS = {
        "廣告投放": "Meta/Google 廣告投放優化，提升 ROAS",
        "SEO優化": "搜尋引擎優化，提升自然流量",
        "社群代操": "FB/IG/LINE 社群經營，提升品牌聲量",
        "整合行銷": "跨通路整合行銷方案，串聯線上線下",
        "KOL行銷": "網紅/KOL 合作行銷，精準觸及目標受眾",
        "程序化廣告": "Programmatic 廣告投放，精準鎖定受眾",
    }
    product_desc = PRODUCTS.get(body.product, body.product)

    tone_map = {"professional": "專業正式", "friendly": "親切友善", "urgent": "急迫有力"}
    tone_label = tone_map.get(body.tone, "專業正式")

    prompt = f"""
你是潮網科技（Wavenet Technology）的資深業務顧問。
請為以下潛在客戶撰寫一封專業的開發提案信（繁體中文）。

## 客戶資訊
- 公司：{lead.company_name}
- 聯絡人：{lead.contact_name or '您好'}
- 職稱：{lead.title or '行銷主管'}
- 產業：{lead.industry or '數位行銷'}
- 官網：{lead.website or '未知'}
- 含金量分數：{score}/100

## 客戶現況分析（從官網偵測）
- Google Tag Manager：{"已安裝" if has_gtm else "未安裝"}
- Meta Pixel：{"已安裝" if has_pixel else "未安裝"}
- GA4：{"已安裝" if has_ga4 else "未安裝"}
- Meta 廣告：{"有在投放" if has_meta_ads else "未偵測到"}
- Google 廣告：{"有在投放" if has_google_ads else "未偵測到"}

## 主推服務
{body.product}：{product_desc}

## 提案信要求
1. 主旨（subject）：吸引注意，提及客戶公司名稱，不超過 15 字
2. 正文（body）：
   - 開場：提及對該公司的了解（基於現況分析）
   - 現況痛點：指出 1-2 個可改善的地方（根據偵測結果）
   - 解決方案：說明潮網如何幫助（主推 {body.product}）
   - 成功案例：簡短提及潮網過往成效（可虛構合理數字）
   - CTA：約定時間電話/視訊討論，留下聯絡方式
   - 簽名：潮網科技業務團隊

語氣：{tone_label}
長度：300-400 字

請輸出 JSON：
{{"subject": "信件主旨", "body": "信件正文（保留換行）", "key_points": ["重點1", "重點2", "重點3"]}}
"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        data = json.loads(raw)
        return {
            "subject": data.get("subject", ""),
            "body": data.get("body", ""),
            "key_points": data.get("key_points", []),
            "lead_id": body.lead_id,
            "product": body.product,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成失敗：{str(e)}")
