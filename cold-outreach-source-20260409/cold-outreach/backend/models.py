import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum, Integer, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import enum

from database import Base
from utils import now_tw


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    team_lead = "team_lead"
    sales = "sales"


class LeadStatus(str, enum.Enum):
    new = "new"
    claiming = "claiming"
    contacted = "contacted"
    called_no_answer = "called_no_answer"
    replied = "replied"
    meeting_scheduled = "meeting_scheduled"
    mql = "mql"
    sql = "sql"
    closed_won = "closed_won"
    closed_lost = "closed_lost"
    won = "won"
    lost = "lost"


class ActivityType(str, enum.Enum):
    email_sent = "email_sent"
    call_note = "call_note"
    meeting_note = "meeting_note"
    status_change = "status_change"


class ScraperJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=now_tw)

    members = relationship("User", back_populates="team")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.sales)
    gmail_token = Column(Text, nullable=True)
    threads_cookie = Column(Text, nullable=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    created_at = Column(DateTime, default=now_tw)

    team = relationship("Team", back_populates="members")
    leads = relationship("Lead", back_populates="assigned_user", foreign_keys="Lead.assigned_to")
    activities = relationship("LeadActivity", back_populates="creator")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    industry = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(SAEnum(LeadStatus), nullable=False, default=LeadStatus.new)
    notes = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    score_reason = Column(Text, nullable=True)
    linkedin = Column(String(500), nullable=True)
    engagement_score = Column(Integer, default=0)
    # Round 6: 含金量欄位
    ad_signals = Column(JSON, nullable=True)      # 廣告投放訊號
    tech_signals = Column(JSON, nullable=True)    # 技術追蹤訊號
    social_signals = Column(JSON, nullable=True)  # 社群數據（純社群）
    ops_signals = Column(JSON, nullable=True)     # 積極營運訊號
    market_signals = Column(JSON, nullable=True)  # 市場體量訊號
    wallet_signals = Column(JSON, nullable=True)  # 口袋深度訊號
    enriched_score = Column(Integer, nullable=True)  # 含金量分數 0-100
    # 公司基本資料
    tax_id = Column(String(20), nullable=True)         # 統一編號（統編）
    representative_name = Column(String(255), nullable=True)  # 代表人姓名
    capital_amount = Column(String(50), nullable=True)  # 資本總額(元)
    created_at = Column(DateTime, default=now_tw)
    updated_at = Column(DateTime, default=now_tw, onupdate=now_tw)

    assigned_user = relationship("User", back_populates="leads", foreign_keys=[assigned_to])
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    enrollments = relationship("SequenceEnrollment", back_populates="lead", cascade="all, delete-orphan")
    pending_emails = relationship("PendingEmail", back_populates="lead", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="lead", cascade="all, delete-orphan")
    lead_tags = relationship("LeadTag", back_populates="lead", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="lead", cascade="all, delete-orphan")


class PendingLeadApproval(Base):
    """同公司不同部門新增名單時，需小組長與 Ivy 張雙人審核才能建立。"""
    __tablename__ = "pending_lead_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime, default=now_tw)
    lead_data = Column(JSON, nullable=False)               # 送審的 LeadCreate payload
    conflict_company = Column(String(255), nullable=False) # 觸發衝突的公司名
    conflict_lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/rejected

    # 小組長審核
    team_lead_decision = Column(String(20), nullable=True)   # approved / rejected
    team_lead_reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Ivy 張審核
    ivy_decision = Column(String(20), nullable=True)
    ivy_reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    review_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    submitter = relationship("User", foreign_keys=[submitted_by])
    team_lead_reviewer = relationship("User", foreign_keys=[team_lead_reviewer_id])
    ivy_reviewer = relationship("User", foreign_keys=[ivy_reviewer_id])


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    type = Column(SAEnum(ActivityType), nullable=False)
    content = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", back_populates="activities")
    creator = relationship("User", back_populates="activities")


class EmailSequence(Base):
    __tablename__ = "email_sequences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    steps = Column(Text, nullable=False)  # JSON: [{day, template_type}]
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_tw)

    enrollments = relationship("SequenceEnrollment", back_populates="sequence", cascade="all, delete-orphan")


class SequenceEnrollment(Base):
    __tablename__ = "sequence_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    sequence_id = Column(UUID(as_uuid=True), ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False)
    current_step = Column(Integer, default=0)
    enrolled_at = Column(DateTime, default=now_tw)
    next_send_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="active")  # active / completed / paused
    enrolled_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    lead = relationship("Lead", back_populates="enrollments")
    sequence = relationship("EmailSequence", back_populates="enrollments")
    pending_emails = relationship("PendingEmail", back_populates="enrollment", cascade="all, delete-orphan")


class PendingEmail(Base):
    __tablename__ = "pending_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("sequence_enrollments.id", ondelete="CASCADE"), nullable=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending / sent / skipped
    created_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", back_populates="pending_emails")
    enrollment = relationship("SequenceEnrollment", back_populates="pending_emails")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    template_type = Column(String(50), nullable=False, default="intro")  # intro/followup/proposal/custom
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_tw)


class ManagerScope(Base):
    """主管可管理的組（部→組）：主管只看得到這些組成員的名單；未設定則看全部。"""
    __tablename__ = "manager_scopes"

    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)


class LeadDevelopment(Base):
    """開發中鎖定：業務在爬蟲預覽頁勾選名單即建立，24 小時未進展自動釋放。"""
    __tablename__ = "lead_developments"

    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True)
    developer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, default=now_tw)


class SentTemplateLog(Base):
    """小郵差群發紀錄：同一家公司同一模板只發一次（防重複寄送）。"""
    __tablename__ = "sent_template_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_norm = Column(String(255), nullable=False, index=True)   # 正規化後的公司名
    company_name = Column(String(255), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    template_name = Column(String(100), nullable=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    sent_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime, default=now_tw)


class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")  # pending / sent / failed
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", foreign_keys=[lead_id])


class EmailOpen(Base):
    __tablename__ = "email_opens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(String(255), nullable=False)  # activity id or scheduled_email id
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    opened_at = Column(DateTime, default=now_tw)
    ip = Column(String(50), nullable=True)

    lead = relationship("Lead", foreign_keys=[lead_id])


class ScraperJob(Base):
    __tablename__ = "scraper_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)   # taitra | meet_taipei | twaa | dma
    url = Column(Text, nullable=False)
    status = Column(SAEnum(ScraperJobStatus), nullable=False, default=ScraperJobStatus.pending)
    result_json = Column(Text, nullable=True)      # JSON array of scraped companies
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_tw)
    updated_at = Column(DateTime, default=now_tw, onupdate=now_tw)


# ── Round 1: CRM 深化 ─────────────────────────────────────────────────────────

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    title = Column(String(255))
    email = Column(String(255))
    phone = Column(String(100))
    linkedin = Column(String(500))
    notes = Column(Text)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", back_populates="contacts")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), default="#6366f1")

    lead_tags = relationship("LeadTag", back_populates="tag", cascade="all, delete-orphan")


class LeadTag(Base):
    __tablename__ = "lead_tags"

    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    lead = relationship("Lead", back_populates="lead_tags")
    tag = relationship("Tag", back_populates="lead_tags")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(100))
    file_data = Column(Text, nullable=True)  # base64 encoded, max 5MB; nullable for Drive links
    drive_url = Column(String(1000), nullable=True)   # Google Drive 連結
    drive_name = Column(String(500), nullable=True)   # Drive 檔案名稱（手動輸入）
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", back_populates="attachments")
    uploader = relationship("User", foreign_keys=[uploaded_by])


# ── Round 2: 自動化 & 整合 ────────────────────────────────────────────────────

class ABTest(Base):
    __tablename__ = "ab_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    subject_a = Column(Text, nullable=False)
    body_a = Column(Text, nullable=False)
    subject_b = Column(Text, nullable=False)
    body_b = Column(Text, nullable=False)
    status = Column(String(50), default="running")  # running/completed
    sent_a = Column(Integer, default=0)
    sent_b = Column(Integer, default=0)
    opened_a = Column(Integer, default=0)
    opened_b = Column(Integer, default=0)
    replied_a = Column(Integer, default=0)
    replied_b = Column(Integer, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=now_tw)

    creator = relationship("User", foreign_keys=[created_by])


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255))
    url = Column(String(1000), nullable=False)
    events = Column(ARRAY(String))  # ["lead.status_changed", "lead.won", "email.replied"]
    is_active = Column(Boolean, default=True)
    secret = Column(String(255))  # HMAC signature secret
    created_at = Column(DateTime, default=now_tw)


class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    event = Column(String(100))
    payload = Column(Text)
    response_status = Column(Integer)
    created_at = Column(DateTime, default=now_tw)

    webhook = relationship("Webhook", foreign_keys=[webhook_id])


# ── Round 3: 智能分析升級 ─────────────────────────────────────────────────────

class KeywordTracker(Base):
    __tablename__ = "keyword_trackers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"))
    keywords = Column(ARRAY(String))  # ["SEO", "數位行銷", "電商"]
    website_url = Column(String(1000))
    last_checked = Column(DateTime)
    last_result = Column(JSON)  # {keyword: found/not_found, context: "..."}
    created_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", foreign_keys=[lead_id])


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start = Column(DateTime, nullable=False)
    week_end = Column(DateTime, nullable=False)
    content = Column(Text)  # Markdown
    stats_snapshot = Column(JSON)  # {sent, replied, won, new_leads, ...}
    created_at = Column(DateTime, default=now_tw)


# ── Round 4: Cadence 波段引擎 ─────────────────────────────────────────────────

class CadenceStepType(str, enum.Enum):
    email = "email"
    call = "call"
    linkedin = "linkedin"
    sms = "sms"


class Cadence(Base):
    __tablename__ = "cadences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    steps = Column(JSON)  # [{day: 1, type: "email", template_id: "...", note: "..."}, ...]
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=now_tw)

    creator = relationship("User", foreign_keys=[created_by])
    enrollments = relationship("CadenceEnrollment", back_populates="cadence", cascade="all, delete-orphan")


class CadenceEnrollment(Base):
    __tablename__ = "cadence_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cadence_id = Column(UUID(as_uuid=True), ForeignKey("cadences.id", ondelete="CASCADE"))
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"))
    current_step = Column(Integer, default=0)
    status = Column(String(50), default="active")  # active/paused/completed
    enrolled_at = Column(DateTime, default=now_tw)
    next_action_at = Column(DateTime)
    completed_at = Column(DateTime)

    cadence = relationship("Cadence", back_populates="enrollments")
    lead = relationship("Lead", foreign_keys=[lead_id])
    step_logs = relationship("CadenceStepLog", back_populates="enrollment", cascade="all, delete-orphan")


class CadenceStepLog(Base):
    __tablename__ = "cadence_step_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("cadence_enrollments.id", ondelete="CASCADE"))
    step_index = Column(Integer)
    step_type = Column(String(50))
    status = Column(String(50), default="pending")  # pending/done/skipped
    note = Column(Text)
    executed_at = Column(DateTime)
    created_at = Column(DateTime, default=now_tw)

    enrollment = relationship("CadenceEnrollment", back_populates="step_logs")


# ── Round 4: 互動數據深化 ─────────────────────────────────────────────────────

class EmailClick(Base):
    __tablename__ = "email_clicks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(String(255))
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    url = Column(String(2000))
    clicked_at = Column(DateTime, default=now_tw)
    ip = Column(String(50))

    lead = relationship("Lead", foreign_keys=[lead_id])


# ── ICP Profiles ──────────────────────────────────────────────────────────────

class ICPProfile(Base):
    __tablename__ = "icp_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    industries = Column(ARRAY(String), default=[])
    company_sizes = Column(ARRAY(String), default=[])
    titles = Column(ARRAY(String), default=[])
    locations = Column(ARRAY(String), default=[])
    created_at = Column(DateTime, default=now_tw)


# ── Round 4: 通話記錄 ──────────────────────────────────────────────────────────

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"))
    caller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    duration_seconds = Column(Integer)
    outcome = Column(String(100))  # answered/no_answer/voicemail/callback_requested
    note = Column(Text)
    called_at = Column(DateTime, default=now_tw)

    lead = relationship("Lead", foreign_keys=[lead_id])
    caller = relationship("User", foreign_keys=[caller_id])


# ── 提案管理 ───────────────────────────────────────────────────────────────────

class ProposalStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    product_focus = Column(String(255), nullable=True)   # 主推服務
    budget_range = Column(String(100), nullable=True)    # 預算區間
    status = Column(SAEnum(ProposalStatus), nullable=False, default=ProposalStatus.draft)
    content = Column(JSON, nullable=True)                # 5-phase structured content
    email_subject = Column(String(500), nullable=True)   # 配套開發信主旨
    email_body = Column(Text, nullable=True)             # 配套開發信內文
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_tw)
    updated_at = Column(DateTime, default=now_tw, onupdate=now_tw)

    lead = relationship("Lead", foreign_keys=[lead_id])
    creator = relationship("User", foreign_keys=[created_by])
