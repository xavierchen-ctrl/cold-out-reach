from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr
from models import UserRole, LeadStatus, ActivityType, ScraperJobStatus


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


# ── Lead ──────────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    company_name: str
    contact_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    company_size: Optional[str] = None
    source: Optional[str] = None
    assigned_to: Optional[UUID] = None
    notes: Optional[str] = None
    tax_id: Optional[str] = None
    representative_name: Optional[str] = None
    capital_amount: Optional[str] = None


class LeadUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    company_size: Optional[str] = None
    source: Optional[str] = None
    assigned_to: Optional[UUID] = None
    status: Optional[LeadStatus] = None
    notes: Optional[str] = None
    tax_id: Optional[str] = None
    representative_name: Optional[str] = None
    capital_amount: Optional[str] = None


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadOut(BaseModel):
    id: UUID
    company_name: str
    contact_name: Optional[str]
    title: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str] = None
    linkedin: Optional[str] = None
    industry: Optional[str]
    city: Optional[str]
    company_size: Optional[str]
    source: Optional[str]
    assigned_to: Optional[UUID]
    status: LeadStatus
    notes: Optional[str]
    score: Optional[int] = None
    score_reason: Optional[str] = None
    engagement_score: Optional[int] = None
    # Round 6: 含金量欄位
    ad_signals: Optional[Any] = None
    tech_signals: Optional[Any] = None
    social_signals: Optional[Any] = None
    ops_signals: Optional[Any] = None
    market_signals: Optional[Any] = None
    wallet_signals: Optional[Any] = None
    enriched_score: Optional[int] = None
    tax_id: Optional[str] = None
    representative_name: Optional[str] = None
    capital_amount: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    assigned_user: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ── Scoring ───────────────────────────────────────────────────────────────────

class ScoreResponse(BaseModel):
    lead_id: UUID
    score: int
    score_reason: str
    updated_at: datetime


# ── Activity ──────────────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    type: ActivityType
    content: Optional[str] = None


class ActivityOut(BaseModel):
    id: UUID
    lead_id: UUID
    type: ActivityType
    content: Optional[str]
    created_by: UUID
    created_at: datetime
    creator: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ── Gmail ─────────────────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    lead_id: UUID
    to: str
    subject: str
    body: str


# ── AI ────────────────────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    lead_id: UUID
    template_type: str  # intro / followup / proposal


class DraftResponse(BaseModel):
    subject: str
    body: str


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsOverview(BaseModel):
    total_leads: int
    new: int
    contacted: int
    replied: int
    meeting_scheduled: int
    won: int
    lost: int
    emails_sent_this_week: int


class SalesStat(BaseModel):
    user_id: UUID
    name: str
    total: int
    won: int
    contacted: int
    replied: int = 0
    contact_rate: float = 0.0
    reply_rate: float = 0.0


class FunnelStage(BaseModel):
    status: str
    count: int


# ── Scraper ───────────────────────────────────────────────────────────────────

class ScraperRunRequest(BaseModel):
    source: str
    url: Optional[str] = None
    keyword: Optional[str] = None       # 自訂關鍵字，e.g. "電商", "品牌行銷"
    industry: Optional[str] = None      # 自訂產業標籤，e.g. "零售業", "科技業"
    limit: Optional[int] = 100          # 最多抓幾筆（預設 100）


class ScrapedCompany(BaseModel):
    company_name: str
    contact_name: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = "數位行銷"


class ScraperJobOut(BaseModel):
    id: UUID
    source: str
    url: str
    status: ScraperJobStatus
    count: Optional[int] = None   # number of companies scraped
    error_msg: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScraperImportRequest(BaseModel):
    assigned_to: Optional[UUID] = None
    email_only: Optional[bool] = False
