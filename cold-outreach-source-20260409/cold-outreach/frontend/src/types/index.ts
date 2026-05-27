export type UserRole = 'admin' | 'manager' | 'sales'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  created_at: string
}

export type LeadStatus =
  | 'new'
  | 'contacted'
  | 'replied'
  | 'meeting_scheduled'
  | 'mql'
  | 'sql'
  | 'closed_won'
  | 'closed_lost'
  | 'won'
  | 'lost'

export const LEAD_STATUS_LABELS: Record<LeadStatus, string> = {
  new: '新名單',
  contacted: '已聯繫',
  replied: '已回覆',
  meeting_scheduled: '會議確認',
  mql: 'MQL 行銷合格',
  sql: 'SQL 銷售合格',
  closed_won: '成交關閉',
  closed_lost: '流失關閉',
  won: '成交',
  lost: '放棄',
}

export const LEAD_STATUS_COLORS: Record<LeadStatus, string> = {
  new: 'bg-gray-100 text-gray-700',
  contacted: 'bg-blue-100 text-blue-700',
  replied: 'bg-yellow-100 text-yellow-700',
  meeting_scheduled: 'bg-purple-100 text-purple-700',
  mql: 'bg-orange-100 text-orange-700',
  sql: 'bg-indigo-100 text-indigo-700',
  closed_won: 'bg-green-200 text-green-800',
  closed_lost: 'bg-red-200 text-red-800',
  won: 'bg-green-100 text-green-700',
  lost: 'bg-red-100 text-red-700',
}

// ── ICP Profile ────────────────────────────────────────────────────────────────

export interface ICPProfile {
  id: string
  name: string
  industries: string[]
  company_sizes: string[]
  titles: string[]
  locations: string[]
  created_at: string
}

export interface Lead {
  id: string
  company_name: string
  contact_name: string | null
  title: string | null
  email: string | null
  phone: string | null
  industry: string | null
  city: string | null
  company_size: string | null
  source: string | null
  assigned_to: string | null
  status: LeadStatus
  notes: string | null
  score: number | null
  score_reason: string | null
  linkedin: string | null
  website?: string | null
  engagement_score: number
  // Round 6: 含金量欄位
  ad_signals?: Record<string, any> | null
  tech_signals?: Record<string, any> | null
  social_signals?: Record<string, any> | null
  ops_signals?: Record<string, any> | null
  market_signals?: Record<string, any> | null
  wallet_signals?: Record<string, any> | null
  enriched_score?: number | null
  tax_id?: string | null
  representative_name?: string | null
  capital_amount?: string | null
  created_at: string
  updated_at: string
  assigned_user?: User | null
}

export type ActivityType = 'email_sent' | 'call_note' | 'meeting_note' | 'status_change'

export const ACTIVITY_LABELS: Record<ActivityType, string> = {
  email_sent: '發送郵件',
  call_note: '通話記錄',
  meeting_note: '會議記錄',
  status_change: '狀態變更',
}

export interface Activity {
  id: string
  lead_id: string
  type: ActivityType
  content: string | null
  created_by: string
  created_at: string
  creator?: User | null
}

export type ScraperJobStatus = 'pending' | 'running' | 'done' | 'failed'

export const SCRAPER_SOURCES: Record<string, string> = {
  apollo: 'Apollo.io（B2B 聯絡人 + Email）',
  lusha: 'Lusha（電話 + Email）',
  job_104: '104 人力銀行',
  job_1111: '1111 人力銀行',
  real_estate_591: '591 新成屋（建商電話）',
  custom_url: '自訂網址',
}

export const SCRAPER_DEFAULT_URLS: Record<string, string> = {
  apollo: 'apollo_search',
  lusha: 'lusha_enrich',
  job_104: 'https://www.104.com.tw/jobs/search/api/jobs?keyword=數位行銷',
  job_1111: 'https://www.1111.com.tw/search/job?ks=數位行銷',
  real_estate_591: 'https://newhouse.591.com.tw',
  custom_url: 'https://',
}

export interface ScraperJob {
  id: string
  source: string
  url: string
  status: ScraperJobStatus
  count: number | null
  error_msg: string | null
  created_at: string
  updated_at: string
}

export interface StatsOverview {
  total_leads: number
  new: number
  contacted: number
  replied: number
  meeting_scheduled: number
  won: number
  lost: number
  emails_sent_this_week: number
}

export interface SalesStat {
  user_id: string
  name: string
  total: number
  won: number
  contacted: number
}

export interface FunnelStage {
  status: string
  count: number
}

// ── Email Templates ───────────────────────────────────────────────────────────

export interface EmailTemplate {
  id: string
  name: string
  subject: string
  body: string
  template_type: string
  created_by: string | null
  created_at: string
}

// ── Scheduled Emails ──────────────────────────────────────────────────────────

export interface ScheduledEmail {
  id: string
  lead_id: string
  template_id: string | null
  to_email: string
  subject: string
  body: string
  scheduled_at: string
  sent_at: string | null
  status: string
  created_at: string
}

export interface EmailOpenStatus {
  email_id: string
  opened_at: string
  ip: string | null
}

// ── Sales Performance ─────────────────────────────────────────────────────────

export interface WeeklyPerf {
  week: string
  emails_sent: number
  replies: number
  won: number
}

export interface SalesPerformance {
  user: { id: string; name: string }
  weekly: WeeklyPerf[]
  totals: {
    total_leads: number
    total_won: number
    total_replied: number
    total_emails: number
    win_rate: number
    reply_rate: number
  }
  top_leads: Array<{ id: string; company_name: string; score: number; status: string }>
}

// ── Round 1: CRM 深化 ─────────────────────────────────────────────────────────

export interface Contact {
  id: string
  company_id: string
  name: string
  title: string | null
  email: string | null
  phone: string | null
  linkedin: string | null
  notes: string | null
  is_primary: boolean
  created_at: string
}

export interface Tag {
  id: string
  name: string
  color: string
}

export interface Attachment {
  id: string
  lead_id: string
  filename: string
  file_size: number | null
  file_type: string | null
  drive_url: string | null
  drive_name: string | null
  is_drive_link: boolean
  uploaded_by: string | null
  created_at: string
}

// ── Round 2: 自動化 & 整合 ────────────────────────────────────────────────────

export interface ABTest {
  id: string
  name: string
  subject_a: string
  body_a: string
  subject_b: string
  body_b: string
  status: string
  sent_a: number
  sent_b: number
  opened_a: number
  opened_b: number
  replied_a: number
  replied_b: number
  created_at: string
}

export interface ABTestResult {
  test: ABTest
  a: { sent: number; opened: number; replied: number; open_rate: number; reply_rate: number }
  b: { sent: number; opened: number; replied: number; open_rate: number; reply_rate: number }
  winner: 'A' | 'B' | null
}

export interface Webhook {
  id: string
  name: string | null
  url: string
  events: string[]
  is_active: boolean
  created_at: string
}

export interface WebhookLog {
  id: string
  webhook_id: string
  event: string | null
  payload: string | null
  response_status: number | null
  created_at: string
}

// ── Round 3: 智能分析升級 ─────────────────────────────────────────────────────

export interface HeatmapCell {
  day: number
  hour: number
  sent: number
  replied: number
  reply_rate: number
}

export interface HeatmapRow {
  day_name: string
  hours: HeatmapCell[]
}

export interface BestTime {
  day: number
  day_name: string
  hour: number
  hour_label: string
  sent_count: number
}

export interface KeywordTracker {
  id: string
  lead_id: string | null
  keywords: string[]
  website_url: string | null
  last_checked: string | null
  last_result: Record<string, { found: boolean; count: number; context: string | null }> | null
  created_at: string
}

export interface WeeklyReport {
  id: string
  week_start: string
  week_end: string
  content: string
  stats: {
    this_week: { emails_sent: number; replied: number; won: number; new_leads: number; reply_rate: number }
    last_week: { emails_sent: number; replied: number; won: number; new_leads: number; reply_rate: number }
  }
  created_at: string
}

// ── Round 4: Cadence 波段引擎 ─────────────────────────────────────────────────

export type CadenceStepType = 'email' | 'call' | 'linkedin' | 'sms'

export interface CadenceStep {
  day: number
  type: CadenceStepType
  template_id?: string | null
  subject?: string
  note?: string
}

export interface Cadence {
  id: string
  name: string
  description: string | null
  steps: CadenceStep[]
  step_count: number
  enrollment_count: number
  created_by: string | null
  created_at: string
}

export interface CadenceStepLog {
  id: string
  step_index: number
  step_type: string
  status: 'pending' | 'done' | 'skipped'
  note: string | null
  executed_at: string | null
  created_at: string
}

export interface CadenceEnrollment {
  id: string
  cadence_id: string
  cadence_name: string | null
  lead_id: string
  company_name: string | null
  contact_name: string | null
  email: string | null
  current_step: number
  total_steps: number
  status: 'active' | 'paused' | 'completed'
  enrolled_at: string | null
  next_action_at: string | null
  completed_at: string | null
  current_step_info: CadenceStep | null
  step_logs: CadenceStepLog[]
}

// ── Round 4: 通話記錄 ──────────────────────────────────────────────────────────

export type CallOutcome = 'answered' | 'no_answer' | 'voicemail' | 'callback_requested'

export const CALL_OUTCOME_LABELS: Record<CallOutcome, string> = {
  answered: '接通',
  no_answer: '未接',
  voicemail: '語音信箱',
  callback_requested: '要求回電',
}

export interface CallLog {
  id: string
  lead_id: string
  caller_id: string | null
  caller_name: string | null
  duration_seconds: number | null
  outcome: CallOutcome | null
  note: string | null
  called_at: string
}

// ── Round 4: 活動成效摘要 ─────────────────────────────────────────────────────

export interface CampaignSummary {
  total_leads: number
  contacted: number
  opened: number
  clicked: number
  replied: number
  meeting_scheduled: number
  emails_sent: number
  contact_rate: string
  open_rate: string
  click_rate: string
  reply_rate: string
}
