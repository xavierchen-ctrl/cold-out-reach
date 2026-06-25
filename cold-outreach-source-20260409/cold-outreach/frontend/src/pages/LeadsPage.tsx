import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  getLeads, createLead, updateLead, deleteLead, updateLeadStatus,
  importCSV, downloadLeadTemplate, getActivities, createActivity, getGmailAuthUrl, sendEmail, generateDraft,
  runScraper, getScraperJobs, previewScraperJob, importScraperJob,
  scoreLead, scoreBatch, bulkStatus, bulkDelete, getSequences, enrollSequence, enrichLushaPhone, enrichLushaStatus,
  exportCsv, getUsers, getTags, addLeadTags, getICPs, batchAnalyzeSignals,
  getTemplates, bulkSendEmail,
  getLeadApprovals, getLeadApprovalCount, reviewLeadApproval, ImportConflict,
} from '@/lib/api'
import ConflictReviewDialog from '@/components/ConflictReviewDialog'
import { useAuth } from '@/hooks/useAuth'
import { Lead, LeadStatus, Activity, ScraperJob, User, Tag, ICPProfile, EmailTemplate, LEAD_STATUS_LABELS, LEAD_STATUS_COLORS, SCRAPER_SOURCES, SCRAPER_DEFAULT_URLS, ACTIVITY_LABELS } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Upload, Search, Trash2, Mail, Sparkles, RefreshCw, Download, Eye, Star, CheckSquare, LayoutGrid, Table2, SlidersHorizontal, Building2, Phone } from 'lucide-react'
import KanbanView from '@/components/KanbanView'
import AdvancedFilterSidebar, { FilterChips, FilterState, EMPTY_FILTER, applyFilter } from '@/components/AdvancedFilterSidebar'

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-muted-foreground">—</span>
  const color = score >= 80 ? 'bg-green-100 text-green-700' : score >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
  return <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${color}`}>{score}</span>
}

function isApprover(user?: { role?: string; name?: string } | null) {
  return user?.role === 'team_lead' || user?.role === 'admin' || user?.role === 'manager'
}

// Tabs vary by role: sales cannot see scraper tab; approvers get 待審核 tab
function getAvailableTabs(role?: string, approver?: boolean) {
  const base = ['手動管理', 'CSV 匯入', '名單爬取']
  if (approver) base.push('待審核')
  return base as Tab[]
}
type Tab = '手動管理' | 'CSV 匯入' | '名單爬取' | '待審核'

const STATUS_OPTIONS = Object.entries(LEAD_STATUS_LABELS) as [LeadStatus, string][]
const PIPELINE = Object.keys(LEAD_STATUS_LABELS) as LeadStatus[]
// 篩選下拉隱藏的狀態（已回覆/成交關閉/流失關閉/成交/放棄）
const FILTER_HIDDEN_STATUSES: LeadStatus[] = ['replied', 'closed_won', 'closed_lost', 'lost']
const FILTER_STATUS_OPTIONS = STATUS_OPTIONS.filter(([k]) => !FILTER_HIDDEN_STATUSES.includes(k))

// 從備註萃取 Ragic 接洽人（同步時寫成「Ragic 接洽人：XXX」）
function ragicContact(notes?: string | null): string {
  if (!notes) return ''
  const m = notes.match(/Ragic 接洽人：([^；;\n]+)/)
  return m ? m[1].trim() : ''
}

// 名單的業務名稱：優先系統指派業務，否則 Ragic 帶入的業務
function leadSalesName(lead: Lead): string {
  return lead.assigned_user?.name || ragicContact(lead.notes) || ''
}

// ── Status Badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const color = LEAD_STATUS_COLORS[status as LeadStatus] ?? 'bg-gray-100 text-gray-500'
  const label = LEAD_STATUS_LABELS[status as LeadStatus] ?? status
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  )
}

// ── Lead Detail Panel ─────────────────────────────────────────────────────────
function LeadDetail({
  lead,
  onClose,
  onUpdated,
}: {
  lead: Lead
  onClose: () => void
  onUpdated: () => void
}) {
  const { user } = useAuth()
  const [form, setForm] = useState({ ...lead })
  const [activities, setActivities] = useState<Activity[]>([])
  const [saving, setSaving] = useState(false)
  const [showEmail, setShowEmail] = useState(false)
  const [emailTo, setEmailTo] = useState(lead.email || '')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')
  const [draftTemplate, setDraftTemplate] = useState('intro')
  const [generatingDraft, setGeneratingDraft] = useState(false)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [noteContent, setNoteContent] = useState('')

  const loadActivities = useCallback(async () => {
    const res = await getActivities(lead.id)
    setActivities(Array.isArray(res.data) ? res.data : [])
  }, [lead.id])

  useEffect(() => { loadActivities() }, [loadActivities])

  const save = async () => {
    setSaving(true)
    try {
      await updateLead(lead.id, form)
      onUpdated()
    } finally {
      setSaving(false)
    }
  }

  const changeStatus = async (status: LeadStatus) => {
    await updateLeadStatus(lead.id, status)
    setForm(f => ({ ...f, status }))
    onUpdated()
    loadActivities()
  }

  const handleDraft = async () => {
    setGeneratingDraft(true)
    try {
      const res = await generateDraft(lead.id, draftTemplate)
      setEmailSubject(res.data.subject)
      setEmailBody(res.data.body)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || 'AI 草稿失敗')
    } finally {
      setGeneratingDraft(false)
    }
  }

  const handleSendEmail = async () => {
    setSendingEmail(true)
    try {
      await sendEmail({ lead_id: lead.id, to: emailTo, subject: emailSubject, body: emailBody })
      setShowEmail(false)
      loadActivities()
      alert('郵件已送出')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      const msg = err?.response?.data?.detail || ''
      if (msg.includes('Gmail not connected')) {
        const authRes = await getGmailAuthUrl()
        window.open(authRes.data.auth_url, '_blank')
      } else {
        alert(msg || '發送失敗')
      }
    } finally {
      setSendingEmail(false)
    }
  }

  const addNote = async () => {
    if (!noteContent.trim()) return
    await createActivity(lead.id, { type: 'call_note', content: noteContent })
    setNoteContent('')
    loadActivities()
  }

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[560px] bg-white shadow-xl overflow-y-auto flex flex-col">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">{lead.company_name}</h2>
            <p className="text-sm text-muted-foreground">{lead.contact_name} {lead.title && `· ${lead.title}`}</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>

        <div className="px-6 py-4 border-b">
          <p className="text-xs font-medium text-muted-foreground mb-2">Pipeline</p>
          <div className="flex gap-1 flex-wrap">
            {PIPELINE.map(s => (
              <button
                key={s}
                onClick={() => changeStatus(s)}
                className={`px-2 py-1 rounded text-xs font-medium border transition-colors ${form.status === s ? 'bg-primary text-primary-foreground border-primary' : 'border-input hover:bg-muted'}`}
              >
                {LEAD_STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        <div className="px-6 py-4 space-y-3 border-b">
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: '公司', key: 'company_name' },
              { label: '聯絡人', key: 'contact_name' },
              { label: '部門', key: 'department' },
              { label: '職稱', key: 'title' },
              { label: 'Email', key: 'email' },
              { label: '電話', key: 'phone' },
              { label: '統一編號', key: 'tax_id' },
              { label: '資本額', key: 'capital_amount' },
              { label: '產業', key: 'industry' },
              { label: '城市', key: 'city' },
              { label: '公司規模', key: 'company_size' },
            ].map(({ label, key }) => (
              <div key={key}>
                <Label className="text-xs">{label}</Label>
                <Input
                  value={(form as Record<string, unknown>)[key] as string || ''}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  className="h-8 text-sm mt-0.5"
                />
              </div>
            ))}
          </div>
          {/* 官方網址欄位 (全寬) */}
          <div>
            <Label className="text-xs">官方網址</Label>
            <div className="flex items-center gap-2 mt-0.5">
              <Input
                value={form.website || ''}
                onChange={e => setForm(f => ({ ...f, website: e.target.value }))}
                className="h-8 text-sm flex-1"
                placeholder="https://"
              />
              {form.website && (
                <a
                  href={form.website.startsWith('http') ? form.website : `https://${form.website}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-blue-500 hover:underline whitespace-nowrap shrink-0"
                  onClick={e => e.stopPropagation()}
                >
                  開啟 ↗
                </a>
              )}
            </div>
          </div>
          <div>
            <Label className="text-xs">備注</Label>
            <Textarea
              value={form.notes || ''}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              className="text-sm mt-0.5"
              rows={2}
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button size="sm" onClick={save} disabled={saving}>{saving ? '儲存中...' : '儲存'}</Button>
            <Button size="sm" variant="outline" onClick={() => setShowEmail(true)}>
              <Mail className="w-3.5 h-3.5 mr-1.5" /> 發信
            </Button>
            <Button size="sm" variant="outline" onClick={async () => {
              await scoreLead(lead.id)
              onUpdated()
            }}>
              <Star className="w-3.5 h-3.5 mr-1.5" /> 評分
            </Button>
          </div>
          {lead.score !== null && (
            <div className="mt-2 p-2 bg-muted rounded text-xs">
              <span className="font-medium">評分：</span>
              <ScoreBadge score={lead.score} />
              {lead.score_reason && <span className="ml-2 text-muted-foreground">{lead.score_reason}</span>}
            </div>
          )}
        </div>

        {/* Activity timeline */}
        <div className="px-6 py-4 flex-1">
          <p className="text-xs font-medium text-muted-foreground mb-3">活動記錄</p>
          <div className="flex gap-2 mb-4">
            <Textarea
              placeholder="新增通話/會議備注..."
              value={noteContent}
              onChange={e => setNoteContent(e.target.value)}
              className="text-sm"
              rows={2}
            />
            <Button size="sm" onClick={addNote} className="self-end">新增</Button>
          </div>
          <div className="space-y-3">
            {activities.map(act => (
              <div key={act.id} className="flex gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-primary mt-2 shrink-0" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium">{ACTIVITY_LABELS[act.type]}</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(act.created_at).toLocaleString('zh-TW')}
                    </span>
                  </div>
                  {act.content && <p className="text-sm text-gray-700 mt-0.5 whitespace-pre-wrap">{act.content}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Email Modal */}
      <Dialog open={showEmail} onOpenChange={setShowEmail}>
        <DialogContent className="max-w-xl">
          <DialogHeader><DialogTitle>發送郵件</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>收件人</Label>
              <Input value={emailTo} onChange={e => setEmailTo(e.target.value)} />
            </div>
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <Label>AI 草稿類型</Label>
                <Select value={draftTemplate} onValueChange={setDraftTemplate}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="intro">初次開發</SelectItem>
                    <SelectItem value="followup">追蹤跟進</SelectItem>
                    <SelectItem value="proposal">報價提案</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button variant="outline" size="sm" onClick={handleDraft} disabled={generatingDraft}>
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                {generatingDraft ? '生成中...' : 'AI 草稿'}
              </Button>
            </div>
            <div>
              <Label>主旨</Label>
              <Input value={emailSubject} onChange={e => setEmailSubject(e.target.value)} />
            </div>
            <div>
              <Label>內文</Label>
              <Textarea value={emailBody} onChange={e => setEmailBody(e.target.value)} rows={8} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowEmail(false)}>取消</Button>
              <Button onClick={handleSendEmail} disabled={sendingEmail}>
                {sendingEmail ? '發送中...' : '發送'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Create Lead Modal ─────────────────────────────────────────────────────────
function CreateLeadModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ company_name: '', contact_name: '', title: '', email: '', phone: '', industry: '', city: '', department: '', source: '' })
  const [saving, setSaving] = useState(false)
  const [pendingMsg, setPendingMsg] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await createLead(form)
      if (res.status === 202 && res.data?.pending_approval) {
        setPendingMsg(res.data.message)
      } else {
        onCreated()
        onClose()
      }
    } finally {
      setSaving(false)
    }
  }

  if (pendingMsg) {
    return (
      <Dialog open onOpenChange={onClose}>
        <DialogContent>
          <DialogHeader><DialogTitle>審核申請已送出</DialogTitle></DialogHeader>
          <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-4 text-sm text-yellow-800">{pendingMsg}</div>
          <div className="flex justify-end pt-2">
            <Button onClick={onClose}>關閉</Button>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader><DialogTitle>新增名單</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <Label>公司名稱 *</Label>
            <Input value={form.company_name} onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: '聯絡人', key: 'contact_name' },
              { label: '職稱', key: 'title' },
              { label: 'Email', key: 'email' },
              { label: '電話', key: 'phone' },
              { label: '產業', key: 'industry' },
              { label: '城市', key: 'city' },
              { label: '部門', key: 'department' },
            ].map(({ label, key }) => (
              <div key={key}>
                <Label>{label}</Label>
                <Input
                  value={(form as Record<string, unknown>)[key] as string || ''}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  className="h-8 text-sm"
                />
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>取消</Button>
            <Button type="submit" disabled={saving}>{saving ? '新增中...' : '新增'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Approval Tab ──────────────────────────────────────────────────────────────
type ApprovalItem = {
  id: string
  submitted_by_name: string
  submitted_at: string
  conflict_company: string
  lead_data: Record<string, unknown>
  status: string
  team_lead_decision: string | null
  team_lead_reviewer_name: string | null
  ivy_decision: string | null
  ivy_reviewer_name: string | null
  review_note: string | null
  resolved_at: string | null
}

function ApprovalTab({ onResolved }: { onResolved: () => void }) {
  const { user } = useAuth()
  const [items, setItems] = useState<ApprovalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [reviewingId, setReviewingId] = useState<string | null>(null)
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getLeadApprovals()
      setItems(Array.isArray(res.data) ? res.data : [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleReview = async (id: string, decision: 'approved' | 'rejected') => {
    setReviewingId(id)
    try {
      await reviewLeadApproval(id, decision, note || undefined)
      setNote('')
      await load()
      onResolved()
    } finally {
      setReviewingId(null)
    }
  }

  const decisionLabel = (d: string | null) => {
    if (d === 'approved') return <span className="text-green-600 font-medium">核准</span>
    if (d === 'rejected') return <span className="text-red-600 font-medium">拒絕</span>
    return <span className="text-muted-foreground">待審</span>
  }

  if (loading) return <div className="py-12 text-center text-muted-foreground text-sm">載入中…</div>
  if (items.length === 0) return <div className="py-12 text-center text-muted-foreground text-sm">目前沒有待審核的申請</div>

  return (
    <div className="space-y-4">
      {items.map(item => {
        const ld = item.lead_data
        const isPending = item.status === 'pending'
        return (
          <div key={item.id} className={`rounded-lg border p-4 space-y-3 ${isPending ? 'border-yellow-300 bg-yellow-50/40' : 'border-border bg-muted/20'}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full mb-1 ${item.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : item.status === 'approved' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {item.status === 'pending' ? '待審核' : item.status === 'approved' ? '已核准' : '已拒絕'}
                </span>
                <p className="font-medium">{item.conflict_company}</p>
                <p className="text-xs text-muted-foreground">申請人：{item.submitted_by_name}　{new Date(item.submitted_at).toLocaleString('zh-TW')}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 text-sm">
              {(['contact_name', 'title', 'email', 'phone', 'department', 'industry', 'city'] as const).map(k => ld[k] ? (
                <div key={k}><span className="text-muted-foreground text-xs">{k === 'contact_name' ? '聯絡人' : k === 'title' ? '職稱' : k === 'email' ? 'Email' : k === 'phone' ? '電話' : k === 'department' ? '部門' : k === 'industry' ? '產業' : '城市'}：</span>{String(ld[k])}</div>
              ) : null)}
            </div>

            <div className="flex flex-wrap gap-4 text-sm">
              <div>小組長：{decisionLabel(item.team_lead_decision)}{item.team_lead_reviewer_name ? ` (${item.team_lead_reviewer_name})` : ''}</div>
              <div>Manager：{decisionLabel(item.ivy_decision)}{item.ivy_reviewer_name ? ` (${item.ivy_reviewer_name})` : ''}</div>
              {item.review_note && <div className="text-muted-foreground">備註：{item.review_note}</div>}
            </div>

            {isPending && isApprover(user) && (
              <div className="flex items-center gap-2 pt-1">
                <Input
                  placeholder="備註（可選）"
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  className="h-8 text-sm max-w-xs"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="border-green-500 text-green-600 hover:bg-green-50"
                  disabled={reviewingId === item.id}
                  onClick={() => handleReview(item.id, 'approved')}
                >核准</Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-400 text-red-600 hover:bg-red-50"
                  disabled={reviewingId === item.id}
                  onClick={() => handleReview(item.id, 'rejected')}
                >拒絕</Button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── CSV Import Tab ────────────────────────────────────────────────────────────
type CsvImportResult = {
  created: number
  errors: string[]
  skipped_ragic?: { company_name: string; in_table: 'existing' | 'new' }[]
  pending_approval?: number
  skipped_duplicate?: number
}

function CsvImportTab({ onImported }: { onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<CsvImportResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [checkRagic, setCheckRagic] = useState(true)
  const [conflicts, setConflicts] = useState<ImportConflict[]>([])
  const [conflictNewCount, setConflictNewCount] = useState(0)
  const [showConflict, setShowConflict] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleImport = async () => {
    if (!file) return
    setLoading(true)
    try {
      const res = await importCSV(file, checkRagic)
      if (res.data?.needs_review) {
        setConflicts(res.data.conflicts || [])
        setConflictNewCount(res.data.new_count || 0)
        setShowConflict(true)
        return
      }
      setResult(res.data)
      onImported()
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '匯入失敗')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmConflicts = async (actions: Record<string, 'approve' | 'skip'>) => {
    if (!file) return
    setLoading(true)
    try {
      const res = await importCSV(file, checkRagic, { confirmed: true, conflict_actions: actions })
      setShowConflict(false)
      setResult(res.data)
      onImported()
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '匯入失敗')
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadTemplate = async () => {
    setDownloading(true)
    try {
      const res = await downloadLeadTemplate()
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'lead_template.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('下載範本失敗')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="max-w-lg">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-sm text-muted-foreground">
            支援欄位：
            <span className="text-foreground font-medium">公司名稱（必填）</span>、
            部門、聯絡人、職稱、email、電話、產業、城市、公司規模、來源
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="ml-4 shrink-0"
          onClick={handleDownloadTemplate}
          disabled={downloading}
        >
          {downloading ? '下載中...' : '下載 Excel 範本'}
        </Button>
      </div>
      <div
        className="border-2 border-dashed border-input rounded-lg p-8 text-center cursor-pointer hover:border-primary transition-colors"
        onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); setFile(e.dataTransfer.files?.[0] || null) }}
      >
        <Upload className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
        <p className="text-sm font-medium">{file ? file.name : '點擊選擇 CSV / Excel 檔案'}</p>
        <p className="text-xs text-muted-foreground mt-1">或拖曳至此</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={e => setFile(e.target.files?.[0] || null)}
        />
      </div>
      {file && (
        <>
          <label className="mt-4 flex items-center gap-2 text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              checked={checkRagic}
              onChange={e => setCheckRagic(e.target.checked)}
              className="rounded border-gray-300"
            />
            <span>匯入前對 Ragic 中台去重（自動跳過既有客戶與陌開中名單）</span>
          </label>
          <Button className="mt-3 w-full" onClick={handleImport} disabled={loading}>
            {loading ? '匯入中...' : '開始匯入'}
          </Button>
        </>
      )}
      {result && (
        <div className="mt-4 p-4 rounded-lg bg-muted text-sm space-y-2">
          <p className="font-medium">
            ✅ 匯入完成：新增 {result.created} 筆
            {result.pending_approval ? `、送審核 ${result.pending_approval} 筆` : ''}
            {result.skipped_duplicate ? `、跳過重複 ${result.skipped_duplicate} 筆` : ''}
          </p>
          {result.skipped_ragic && result.skipped_ragic.length > 0 && (
            <div>
              <p className="text-amber-700 font-medium">
                跳過 {result.skipped_ragic.length} 筆（已在 Ragic 中台）：
              </p>
              <ul className="pl-4 text-xs text-muted-foreground space-y-0.5 mt-1 max-h-40 overflow-y-auto">
                {result.skipped_ragic.map((s, i) => (
                  <li key={i}>
                    {s.company_name}
                    <span className={`ml-2 inline-block text-[10px] px-1.5 py-0.5 rounded ${
                      s.in_table === 'existing'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-orange-100 text-orange-700'
                    }`}>
                      {s.in_table === 'existing' ? '既有客戶' : '陌開中'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.errors.length > 0 && (
            <div>
              <p className="text-destructive font-medium">錯誤 {result.errors.length} 筆：</p>
              <ul className="list-disc pl-4 text-xs text-muted-foreground space-y-0.5 mt-1">
                {result.errors.slice(0, 5).map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      <ConflictReviewDialog
        open={showConflict}
        conflicts={conflicts}
        newCount={conflictNewCount}
        loading={loading}
        onCancel={() => setShowConflict(false)}
        onConfirm={handleConfirmConflicts}
      />
    </div>
  )
}

// ── Scraper Tab ───────────────────────────────────────────────────────────────
const SCRAPER_SOURCE_ICONS: Record<string, string> = {
  apollo: '⭐',
  lusha: '📞',
  job_104: '💼',
  job_1111: '📋',
  real_estate_591: '🏠',
  gemini_search: '🔍',
  custom_url: '🔗',
}

// 產業標籤選項（名單爬取）
const SCRAPER_INDUSTRY_OPTIONS = [
  '生活消費品', '交通', '服飾時尚', '金融', '建築製造', '政府單位', '政治',
  '美妝', '食品', '娛樂/藝術', '旅遊', '科技', '教育', '零售業', '電子商務',
  '電信', '醫療保健', '新聞傳播', '科學', '公益', '公關公司',
]
const INDUSTRY_OTHER = '其他'

function ScraperTab({ onImported }: { onImported: () => void }) {
  const [source, setSource] = useState('taitra')
  const [url, setUrl] = useState(SCRAPER_DEFAULT_URLS['taitra'])
  const [keyword, setKeyword] = useState('')
  const [industry, setIndustry] = useState('')
  const [industryOther, setIndustryOther] = useState('')
  const [region, setRegion] = useState('')
  const [limit, setLimit] = useState(10)
  const [icps, setIcps] = useState<ICPProfile[]>([])
  const [jobs, setJobs] = useState<ScraperJob[]>([])
  const [running, setRunning] = useState(false)
  const navigate = useNavigate()

  const loadJobs = useCallback(async () => {
    const res = await getScraperJobs()
    setJobs(Array.isArray(res.data) ? res.data : [])
  }, [])

  useEffect(() => { loadJobs() }, [loadJobs])
  useEffect(() => { getICPs().then(r => setIcps(Array.isArray(r.data) ? r.data : [])).catch(() => {}) }, [])

  // Poll for running jobs
  useEffect(() => {
    const hasRunning = jobs.some(j => j.status === 'pending' || j.status === 'running')
    if (!hasRunning) return
    const timer = setInterval(loadJobs, 3000)
    return () => clearInterval(timer)
  }, [jobs, loadJobs])

  const handleRun = async () => {
    setRunning(true)
    try {
      const realIndustry =
        industry === INDUSTRY_OTHER ? industryOther.trim()
        : industry === 'all' ? ''
        : industry
      const kw = [keyword, region].filter(Boolean).join(' ')
      const res = await runScraper(
        source,
        url !== SCRAPER_DEFAULT_URLS[source] ? url : undefined,
        kw || undefined,
        realIndustry || undefined,
        limit
      )
      // 爬蟲同步完成後，直接進入檢視頁面
      await loadJobs()
      if (res?.data?.id && res?.data?.status === 'done') {
        navigate('/scraper/' + res.data.id)
      }
    } finally {
      setRunning(false)
    }
  }

  const handlePreview = (jobId: string) => {
    navigate('/scraper/' + jobId)
  }

  const [conflicts, setConflicts] = useState<ImportConflict[]>([])
  const [conflictNewCount, setConflictNewCount] = useState(0)
  const [showConflict, setShowConflict] = useState(false)
  const [pendingJobId, setPendingJobId] = useState<string | null>(null)
  const [importingJob, setImportingJob] = useState(false)

  const handleImport = async (jobId: string) => {
    const res = await importScraperJob(jobId)
    if (res.data?.needs_review) {
      setConflicts(res.data.conflicts || [])
      setConflictNewCount(res.data.new_count || 0)
      setPendingJobId(jobId)
      setShowConflict(true)
      return
    }
    alert(`✅ 匯入完成：新增 ${res.data.created} 筆，跳過重複 ${res.data.skipped} 筆`)
    onImported()
  }

  const handleConfirmConflicts = async (actions: Record<string, 'approve' | 'skip'>) => {
    if (!pendingJobId) return
    setImportingJob(true)
    try {
      const res = await importScraperJob(pendingJobId, undefined, undefined, undefined, { confirmed: true, conflict_actions: actions })
      setShowConflict(false)
      const pending = res.data.pending_approval || 0
      alert(`✅ 匯入完成：新增 ${res.data.created} 筆，跳過 ${res.data.skipped} 筆${pending ? `，送審核 ${pending} 筆` : ''}`)
      onImported()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '匯入失敗')
    } finally {
      setImportingJob(false)
    }
  }

  const statusColor: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-blue-100 text-blue-600',
    done: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  }
  const statusLabel: Record<string, string> = { pending: '等待中', running: '爬取中', done: '完成', failed: '失敗' }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Run form */}
      <div className="bg-white border rounded-lg p-5 space-y-4">
        <h3 className="font-medium text-sm">新增爬取任務</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>資料來源</Label>
            <Select
              value={source}
              onValueChange={v => {
                setSource(v)
                setUrl(SCRAPER_DEFAULT_URLS[v])
              }}
            >
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(SCRAPER_SOURCES).map(([k, v]) => (
                  <SelectItem key={k} value={k}>
                    <span className="flex items-center gap-2">
                      <span>{SCRAPER_SOURCE_ICONS[k] ?? '🔍'}</span>
                      <span>{v}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {source !== 'gemini_search' && (
            <div>
              <Label>目標 URL</Label>
              <Input
                value={url}
                onChange={e => setUrl(e.target.value)}
                className="mt-1 text-xs"
                placeholder={source === 'custom_url' ? 'https://www.computex.biz/exhibitors' : ''}
              />
              {source === 'custom_url' && (
                <p className="text-xs text-muted-foreground mt-1">請輸入目標網頁 URL（如會展官網、公會名單），AI 自動提取公司名單</p>
              )}
            </div>
          )}
          <div>
            <Label>
              {source === 'gemini_search' ? '搜尋指令' : '關鍵字'}
              <span className="text-muted-foreground font-normal ml-1">
                {source === 'gemini_search' ? '（用自然語言描述你要找的對象）' : '（自訂搜尋詞）'}
              </span>
            </Label>
            {source === 'gemini_search' && (
              <p className="text-xs text-muted-foreground mt-1 mb-1">
                例：「台灣美妝品牌 有618活動」、「有投放關鍵字廣告的保養品牌」、「美妝 YouTube 頻道 訂閱數高」
              </p>
            )}
            <Input
              value={keyword}
              onChange={e => {
                const kw = e.target.value
                setKeyword(kw)
                if (source !== 'gemini_search') {
                  setUrl(prev => {
                    if (!prev) return prev
                    if (kw) {
                      return prev.replace(/([?&](?:q|keyword|ks)=)[^&]*/g, `$1${encodeURIComponent(kw)}`)
                    } else {
                      return SCRAPER_DEFAULT_URLS[source] || prev
                    }
                  })
                }
              }}
              placeholder={
                source === 'gemini_search' ? '美妝品牌 618促銷活動' :
                source === 'lusha' ? '例：benq.com, 91app.com（domain）或 BenQ, 誠品（公司名）' :
                source === 'custom_url' ? '篩選關鍵字（可空白）' :
                '例：DAZN、數位行銷、SEO'
              }
              className="mt-1"
            />
          </div>
          <div>
            <Label>產業標籤 <span className="text-muted-foreground font-normal">（覆蓋爬取到的產業）</span></Label>
            <Select value={industry} onValueChange={setIndustry}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="選擇產業（可空白）" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部產業</SelectItem>
                {SCRAPER_INDUSTRY_OPTIONS.map(o => (
                  <SelectItem key={o} value={o}>{o}</SelectItem>
                ))}
                <SelectItem value={INDUSTRY_OTHER}>其他（請輸入附註）</SelectItem>
              </SelectContent>
            </Select>
            {industry === INDUSTRY_OTHER && (
              <Input
                className="mt-2"
                placeholder="請輸入產業標籤"
                value={industryOther}
                onChange={e => setIndustryOther(e.target.value)}
              />
            )}
          </div>
          <div>
            <Label>地區 <span className="text-muted-foreground font-normal">（選填，會併入搜尋條件）</span></Label>
            <Input
              className="mt-1"
              placeholder="例：台北、台中、高雄"
              value={region}
              onChange={e => setRegion(e.target.value)}
            />
          </div>
          <div>
            <Label>最多筆數</Label>
            <Select value={String(limit)} onValueChange={v => setLimit(Number(v))}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="5">5 筆</SelectItem>
                <SelectItem value="10">10 筆</SelectItem>
                <SelectItem value="20">20 筆</SelectItem>
                <SelectItem value="50">50 筆</SelectItem>
                <SelectItem value="100">100 筆</SelectItem>
                <SelectItem value="200">200 筆</SelectItem>
                <SelectItem value="500">500 筆</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {icps.length > 0 && (
            <div className="col-span-2">
              <Label>套用 ICP <span className="text-muted-foreground font-normal">（自動填入條件）</span></Label>
              <Select onValueChange={icpId => {
                const icp = icps.find(i => i.id === icpId)
                if (!icp) return
                if (icp.industries.length > 0) setIndustry(icp.industries[0])
                if (icp.titles.length > 0) setKeyword(icp.titles.join('、'))
              }}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="選擇 ICP 套用（可選）" />
                </SelectTrigger>
                <SelectContent>
                  {icps.map(icp => (
                    <SelectItem key={icp.id} value={icp.id}>{icp.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <Button onClick={handleRun} disabled={running}>
          <RefreshCw className={`w-4 h-4 mr-2 ${running ? 'animate-spin' : ''}`} />
          {running ? '啟動中...' : '開始爬取'}
        </Button>
      </div>

      {/* Jobs list */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-sm">任務記錄</h3>
          <Button variant="ghost" size="sm" onClick={loadJobs}><RefreshCw className="w-3.5 h-3.5" /></Button>
        </div>
        {jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">尚無任務</p>
        ) : (
          <div className="space-y-2">
            {jobs.map(job => (
              <div key={job.id} className="bg-white border rounded-lg p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColor[job.status]}`}>
                    {job.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse mr-1.5" />}
                    {statusLabel[job.status]}
                  </span>
                  <div>
                    <p className="text-sm font-medium">{SCRAPER_SOURCE_ICONS[job.source] ?? '🔍'} {SCRAPER_SOURCES[job.source] || job.source}</p>
                    <p className="text-xs text-muted-foreground">{new Date(job.created_at).toLocaleString('zh-TW')}</p>
                  </div>
                  {job.count != null && (
                    <span className="text-xs text-muted-foreground">{job.count} 筆</span>
                  )}
                  {job.error_msg && (
                    <span className="text-xs text-destructive">{job.error_msg.slice(0, 60)}</span>
                  )}
                </div>
                {job.status === 'done' && (
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => handlePreview(job.id)}>
                      <Eye className="w-3.5 h-3.5 mr-1" /> 預覽
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <ConflictReviewDialog
        open={showConflict}
        conflicts={conflicts}
        newCount={conflictNewCount}
        loading={importingJob}
        onCancel={() => setShowConflict(false)}
        onConfirm={handleConfirmConflicts}
      />
    </div>
  )
}

// ── Company View ──────────────────────────────────────────────────────────────
function CompanyView({ leads, onSelect }: { leads: Lead[]; onSelect: (lead: Lead) => void }) {
  // Group by company_name
  const groups = leads.reduce<Record<string, Lead[]>>((acc, lead) => {
    const key = lead.company_name || '未知公司'
    if (!acc[key]) acc[key] = []
    acc[key].push(lead)
    return acc
  }, {})

  const companies = Object.entries(groups).map(([name, members]) => {
    const maxScore = Math.max(...members.map(m => m.score ?? 0))
    const lastInteraction = members
      .map(m => m.updated_at)
      .sort()
      .reverse()[0]
    return { name, members, maxScore, lastInteraction }
  }).sort((a, b) => b.maxScore - a.maxScore)

  if (companies.length === 0) {
    return (
      <div className="text-center py-16 text-muted-foreground mt-4">
        <Building2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p className="text-lg">尚無公司資料</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
      {companies.map(({ name, members, maxScore, lastInteraction }) => (
        <div key={name} className="bg-white border rounded-xl p-4 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-muted-foreground" />
              <h3 className="font-semibold text-sm">{name}</h3>
            </div>
            {maxScore > 0 && (
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${maxScore >= 80 ? 'bg-green-100 text-green-700' : maxScore >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'}`}>
                最高 {maxScore}
              </span>
            )}
          </div>
          <div className="space-y-1.5 mb-3">
            {members.map(m => (
              <div
                key={m.id}
                onClick={() => onSelect(m)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted/50 cursor-pointer text-sm"
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${LEAD_STATUS_COLORS[m.status].split(' ')[0].replace('bg-', 'bg-').replace('-100', '-400')}`} />
                <span className="flex-1 truncate">{m.contact_name || '(無聯絡人)'}</span>
                {m.title && <span className="text-xs text-muted-foreground">{m.title}</span>}
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${LEAD_STATUS_COLORS[m.status]}`}>
                  {LEAD_STATUS_LABELS[m.status]}
                </span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
            <span>{members.length} 位聯絡人</span>
            <span>最近互動：{new Date(lastInteraction).toLocaleDateString('zh-TW')}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
// ── 分頁列 ────────────────────────────────────────────────────────────────────
function Pagination({ page, totalPages, total, onPage }: {
  page: number; totalPages: number; total: number; onPage: (p: number) => void
}) {
  return (
    <div className="flex items-center justify-between gap-2 py-3 px-1 text-sm">
      <span className="text-muted-foreground">
        共 <span className="font-medium text-foreground">{total}</span> 筆 · 第 {page} / {totalPages} 頁
      </span>
      <div className="flex items-center gap-1.5">
        <Button size="sm" variant="outline" className="h-7 px-2.5" disabled={page <= 1} onClick={() => onPage(1)}>« 第一頁</Button>
        <Button size="sm" variant="outline" className="h-7 px-2.5" disabled={page <= 1} onClick={() => onPage(page - 1)}>上一頁</Button>
        <Button size="sm" variant="outline" className="h-7 px-2.5" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>下一頁</Button>
        <Button size="sm" variant="outline" className="h-7 px-2.5" disabled={page >= totalPages} onClick={() => onPage(totalPages)}>最後頁 »</Button>
      </div>
    </div>
  )
}

export default function LeadsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user } = useAuth()
  const TABS = getAvailableTabs(user?.role, isApprover(user))
  const initTab = (searchParams.get('tab') as Tab | null)
  const [activeTab, setActiveTab] = useState<Tab>(
    initTab && (TABS as readonly string[]).includes(initTab) ? initTab : '手動管理'
  )
  const [pendingCount, setPendingCount] = useState(0)
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 100
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterSales, setFilterSales] = useState<string>('all')
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [scoringAll, setScoringAll] = useState(false)
  const [sequences, setSequences] = useState<any[]>([])
  const [viewMode, setViewMode] = useState<'table' | 'kanban' | 'company'>('table')
  const [showFilterSidebar, setShowFilterSidebar] = useState(false)
  const [advFilter, setAdvFilter] = useState<FilterState>(EMPTY_FILTER)
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [allTags, setAllTags] = useState<Tag[]>([])
  const [showBulkTagModal, setShowBulkTagModal] = useState(false)

  const [sortContact, setSortContact] = useState(false)  // 預設關閉：讓最新匯入的名單排在最上面，避免被擠到後面

  const loadLeads = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = {}
      if (search) params.search = search
      if (filterStatus !== 'all') params.status = filterStatus
      if (advFilter.tags && advFilter.tags.length > 0) params.tags = advFilter.tags.join(',')
      if (sortContact) params.sort = 'contact_first'
      params.limit = 10000   // 一次載入全部，改用客戶端分頁
      const res = await getLeads(params)
      setLeads(Array.isArray(res.data) ? res.data : [])
    } finally {
      setLoading(false)
    }
  }, [search, filterStatus, advFilter.tags, sortContact])

  useEffect(() => { loadLeads() }, [loadLeads])
  useEffect(() => {
    getSequences().then(r => setSequences(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    getUsers().then(r => setAllUsers(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    getTags().then(r => setAllTags(Array.isArray(r.data) ? r.data : [])).catch(() => {})
    if (isApprover(user)) {
      getLeadApprovalCount().then(r => setPendingCount(r.data?.count ?? 0)).catch(() => {})
    }
  }, [user])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('確定刪除這筆名單？')) return
    await deleteLead(id)
    loadLeads()
  }

  const toggleCheck = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setChecked(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }
  const toggleAll = () => {
    const pageIds = pagedLeads.map(l => l.id)
    const allOnPage = pageIds.length > 0 && pageIds.every(pid => checked.has(pid))
    setChecked(prev => {
      const next = new Set(prev)
      if (allOnPage) pageIds.forEach(pid => next.delete(pid))
      else pageIds.forEach(pid => next.add(pid))
      return next
    })
  }
  const clearChecked = () => setChecked(new Set())

  const handleBulkStatus = async (status: LeadStatus) => {
    await bulkStatus([...checked], status)
    clearChecked(); loadLeads()
  }
  const handleBulkDelete = async () => {
    if (!confirm(`確定刪除選取的 ${checked.size} 筆名單？`)) return
    await bulkDelete([...checked])
    clearChecked(); loadLeads()
  }
  const handleBulkScore = async () => {
    setScoringAll(true)
    try { await scoreBatch([...checked]); loadLeads() }
    finally { setScoringAll(false) }
  }
  const [enriching, setEnriching] = useState(false)
  const [enrichMsg, setEnrichMsg] = useState('')
  const [analyzingAll, setAnalyzingAll] = useState(false)
  const handleLushaEnrich = async () => {
    setEnriching(true)
    setEnrichMsg('啟動中...')
    try {
      const ids = checked.size > 0 ? [...checked] : undefined
      const limit = checked.size > 0 ? checked.size : 20
      const res = await enrichLushaPhone(ids as string[] | undefined, limit)
      const jobId = res.data.job_id
      setEnrichMsg(`執行中（每筆約 12 秒）...`)
      // Polling
      const poll = async () => {
        const s = await enrichLushaStatus(jobId)
        const { status, enriched, skipped, failed, total, progress } = s.data
        setEnrichMsg(`進度 ${progress}/${total}：已補 ${enriched} 筆電話`)
        if (status === 'done') {
          setEnriching(false)
          setEnrichMsg('')
          alert(`✅ Lusha 補電話完成：${enriched} 筆補到電話，${skipped} 筆查無資料，${failed} 筆 API 錯誤`)
          loadLeads()
          clearChecked()
        } else if (status === 'failed') {
          setEnriching(false)
          setEnrichMsg('')
          alert(`❌ Lusha 補電話失敗：${s.data.error}`)
        } else {
          setTimeout(poll, 5000)
        }
      }
      setTimeout(poll, 5000)
    } catch (e) {
      setEnriching(false)
      setEnrichMsg('')
      alert('Lusha 補電話失敗，請稍後再試')
    }
  }

  const handleEnrollSequence = async (seqId: string) => {
    const res = await enrollSequence(seqId, [...checked])
    alert(`已加入序列：${res.data.enrolled} 筆，跳過（已加入）：${res.data.skipped} 筆`)
    clearChecked()
  }
  const handleScoreAll = async () => {
    setScoringAll(true)
    try { await scoreBatch(); loadLeads() }
    finally { setScoringAll(false) }
  }

  const handleBatchAnalyzeSignals = async () => {
    setAnalyzingAll(true)
    try {
      const res = await batchAnalyzeSignals(undefined, true)
      alert(`✅ 含金量分析完成：${res.data.processed} 筆`)
      loadLeads()
    } catch {
      alert('批量分析失敗')
    } finally {
      setAnalyzingAll(false)
    }
  }

  const handleExportCsv = async () => {
    try {
      const res = await exportCsv()
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `leads_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('匯出失敗')
    }
  }

  // 業務篩選選項（系統業務 + Ragic 帶入的業務，去重）
  const salesOptions = Array.from(new Set(leads.map(leadSalesName).filter(Boolean))).sort()
  const filteredLeads = applyFilter(leads, advFilter)
    .filter(l => {
      if (!filterSales || filterSales === 'all') return true
      return leadSalesName(l).toLowerCase().includes(filterSales.toLowerCase())
    })
  const totalPages = Math.max(1, Math.ceil(filteredLeads.length / PAGE_SIZE))
  const pagedLeads = filteredLeads.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // 搜尋 / 篩選改變時回到第 1 頁；頁碼超出範圍時夾回
  useEffect(() => { setPage(1) }, [search, filterStatus, filterSales, sortContact, advFilter])
  useEffect(() => { if (page > totalPages) setPage(totalPages) }, [page, totalPages])

  return (
    <div className="p-3 md:p-6">
      <div className="mb-4 md:mb-6">
        <h1 className="text-xl font-bold">名單管理</h1>
        <p className="text-sm text-muted-foreground mt-0.5">管理你的陌生開發名單</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px flex items-center gap-1.5 ${activeTab === tab ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
          >
            {tab}
            {tab === '待審核' && pendingCount > 0 && (
              <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold leading-none">
                {pendingCount > 9 ? '9+' : pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === '手動管理' && (
        <div className="flex gap-4">
          {/* Advanced filter sidebar */}
          {showFilterSidebar && (
            <AdvancedFilterSidebar
              leads={leads}
              users={allUsers}
              filter={advFilter}
              onChange={setAdvFilter}
              tags={allTags}
            />
          )}

          <div className="flex-1 min-w-0">
          {/* Toolbar */}
          <div className="mb-4 space-y-2">
            {/* Row 1: search + status filter + add button */}
            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative flex-1 min-w-0 max-w-xs">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="搜尋公司 / 聯絡人..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-8"
                />
              </div>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-32 md:w-36"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部狀態</SelectItem>
                  {FILTER_STATUS_OPTIONS.map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="relative">
                <Input
                  list="sales-filter-options"
                  className="w-32 md:w-44"
                  placeholder="🔍 業務（可打字）"
                  value={filterSales === 'all' ? '' : filterSales}
                  onChange={e => setFilterSales(e.target.value || 'all')}
                />
                <datalist id="sales-filter-options">
                  {salesOptions.map(name => <option key={name} value={name} />)}
                </datalist>
              </div>
              <Button
                variant={showFilterSidebar ? 'default' : 'outline'}
                size="sm"
                onClick={() => setShowFilterSidebar(v => !v)}
              >
                <SlidersHorizontal className="w-4 h-4 md:mr-1.5" />
                <span className="hidden md:inline">進階篩選</span>
              </Button>
              <Button onClick={() => setShowCreate(true)}>
                <Plus className="w-4 h-4 md:mr-1.5" />
                <span className="hidden md:inline">新增名單</span>
              </Button>
              {/* View toggle */}
              <div className="flex border rounded-md overflow-hidden ml-auto">
                <button
                  onClick={() => setViewMode('table')}
                  className={`px-2.5 py-1.5 flex items-center gap-1 text-sm transition-colors ${viewMode === 'table' ? 'bg-primary text-primary-foreground' : 'bg-white text-muted-foreground hover:bg-muted'}`}
                  title="列表視圖"
                >
                  <Table2 className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setViewMode('kanban')}
                  className={`px-2.5 py-1.5 flex items-center gap-1 text-sm transition-colors ${viewMode === 'kanban' ? 'bg-primary text-primary-foreground' : 'bg-white text-muted-foreground hover:bg-muted'}`}
                  title="看板視圖"
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setViewMode('company')}
                  className={`px-2.5 py-1.5 flex items-center gap-1 text-sm transition-colors ${viewMode === 'company' ? 'bg-primary text-primary-foreground' : 'bg-white text-muted-foreground hover:bg-muted'}`}
                  title="公司視圖"
                >
                  <Building2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            {/* Row 2: action buttons (hidden on mobile, collapse into row) */}
            <div className="hidden md:flex items-center gap-2 flex-wrap">
              <Button
                variant={sortContact ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSortContact(v => !v)}
                title="有電話+Email的名單排前面"
              >
                📞 {sortContact ? '聯絡資訊優先 ✓' : '聯絡資訊優先'}
              </Button>
              <Button variant="outline" size="sm" onClick={handleScoreAll} disabled={scoringAll}>
                <Star className={`w-4 h-4 mr-1.5 ${scoringAll ? 'animate-spin' : ''}`} />
                {scoringAll ? '評分中...' : '批量評分'}
              </Button>
              <Button variant="outline" size="sm" onClick={handleLushaEnrich} disabled={enriching}>
                <RefreshCw className={`w-4 h-4 mr-1.5 ${enriching ? 'animate-spin' : ''}`} />
                {enriching ? (enrichMsg || 'Lusha 補電話中...') : '📞 Lusha 補電話'}
              </Button>
              <Button variant="outline" size="sm" onClick={handleBatchAnalyzeSignals} disabled={analyzingAll}>
                🔍 {analyzingAll ? '分析中...' : '批量含金量分析'}
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportCsv}>
                <Download className="w-4 h-4 mr-1.5" /> 匯出 CSV
              </Button>
            </div>
          </div>

          {/* Filter chips */}
          <FilterChips filter={advFilter} onChange={setAdvFilter} />

          {/* Batch action bar */}
          {checked.size > 0 && (
            <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-indigo-50 border border-indigo-200 rounded-lg text-sm flex-wrap">
              <span className="font-medium text-indigo-700">已選 {checked.size} 筆</span>
              <div className="flex gap-2 flex-wrap">
                <Select onValueChange={handleBulkStatus}>
                  <SelectTrigger className="h-7 text-xs w-32"><SelectValue placeholder="改狀態" /></SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
                {sequences.length > 0 && (
                  <Select onValueChange={handleEnrollSequence}>
                    <SelectTrigger className="h-7 text-xs w-36"><SelectValue placeholder="加入序列" /></SelectTrigger>
                    <SelectContent>
                      {sequences.map((s: any) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )}
                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={handleBulkScore} disabled={scoringAll}>
                  <Star className="w-3 h-3 mr-1" /> 評分
                </Button>
                {allTags.length > 0 && (
                  <Select onValueChange={async (tagId) => {
                    const promises = [...checked].map(leadId => addLeadTags(leadId, [tagId]))
                    await Promise.all(promises)
                    alert(`✅ 已為 ${checked.size} 筆名單加上標籤`)
                  }}>
                    <SelectTrigger className="h-7 text-xs w-28"><SelectValue placeholder="加標籤" /></SelectTrigger>
                    <SelectContent>
                      {allTags.map(tag => (
                        <SelectItem key={tag.id} value={tag.id}>
                          <span className="flex items-center gap-1.5">
                            <span className="w-3 h-3 rounded-full inline-block flex-shrink-0" style={{ backgroundColor: tag.color }} />
                            {tag.name}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={handleLushaEnrich} disabled={enriching}>
                  <RefreshCw className={`w-3 h-3 mr-1 ${enriching ? 'animate-spin' : ''}`} />
                  {enriching ? (enrichMsg || '補電話中...') : '📞 Lusha 補電話'}
                </Button>
                {user?.role !== 'sales' && (
                  <Button size="sm" variant="destructive" className="h-7 text-xs" onClick={handleBulkDelete}>
                    <Trash2 className="w-3 h-3 mr-1" /> 刪除
                  </Button>
                )}
                <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={clearChecked}>取消</Button>
              </div>
            </div>
          )}

          {loading ? (
            <p className="text-sm text-muted-foreground mt-4">載入中...</p>
          ) : viewMode === 'kanban' ? (
            <div className="mt-4">
              <KanbanView leads={filteredLeads} onUpdate={loadLeads} />
            </div>
          ) : viewMode === 'company' ? (
            <CompanyView leads={filteredLeads} onSelect={lead => navigate(`/leads/${lead.id}`)} />
          ) : filteredLeads.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground mt-4">
              <p className="text-lg">尚無名單</p>
              <p className="text-sm mt-1">點擊「新增名單」或透過 CSV 匯入</p>
            </div>
          ) : (
            <>
              {/* 手機版：card list */}
              <div className="lg:hidden space-y-3 mt-4">
                {pagedLeads.map(lead => {
                  const canAccess = isApprover(user) || user?.id === lead.assigned_to || lead.status === 'claiming'
                  return (
                  <div
                    key={lead.id}
                    className={`bg-white rounded-lg border p-4 shadow-sm ${canAccess ? 'cursor-pointer active:bg-gray-50' : 'cursor-default opacity-80'}`}
                    onClick={() => { if (canAccess) navigate(`/leads/${lead.id}`) }}
                  >
                    <div className="flex justify-between items-start">
                      <div className="min-w-0 flex-1 mr-2">
                        <h3 className="font-medium truncate">{lead.company_name}</h3>
                        <p className="text-sm text-gray-500 truncate">{lead.contact_name || '—'}</p>
                      </div>
                      <StatusBadge status={lead.status} />
                    </div>
                    <div className="mt-2 text-sm text-gray-600 space-y-0.5">
                      {lead.email && <p className="truncate">✉️ {lead.email}</p>}
                      {lead.phone && <p>📞 {lead.phone}</p>}
                    </div>
                    {lead.enriched_score != null && (
                      <div className="mt-2">
                        <div className="text-xs text-gray-500">含金量 🏆</div>
                        <div className="flex items-center gap-2 mt-1">
                          <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                            <div
                              className={`h-1.5 rounded-full ${lead.enriched_score >= 70 ? 'bg-green-500' : lead.enriched_score >= 40 ? 'bg-yellow-400' : 'bg-gray-400'}`}
                              style={{ width: `${lead.enriched_score}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">{lead.enriched_score}</span>
                        </div>
                      </div>
                    )}
                    <div className="mt-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ScoreBadge score={lead.score} />
                        {!canAccess && <span className="text-xs text-gray-400">🔒</span>}
                      </div>
                      {user?.role !== 'sales' && (
                        <button
                          onClick={e => handleDelete(lead.id, e)}
                          className="text-muted-foreground hover:text-destructive transition-colors p-1"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  )
                })}
                <Pagination page={page} totalPages={totalPages} total={filteredLeads.length} onPage={setPage} />
              </div>

              {/* 桌面版：原有 table */}
              <div className="hidden lg:block">
                <div className="bg-white rounded-lg border overflow-hidden mt-4">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-muted-foreground">
                      <tr>
                        <th className="px-3 py-3 w-8">
                          <input type="checkbox" checked={pagedLeads.length > 0 && pagedLeads.every(l => checked.has(l.id))} onChange={toggleAll} className="rounded" />
                        </th>
                        <th className="px-4 py-3 text-left font-medium">公司</th>
                        <th className="px-4 py-3 text-left font-medium">聯絡人</th>
                        <th className="px-4 py-3 text-left font-medium">Email</th>
                        <th className="px-4 py-3 text-left font-medium">電話</th>
                        <th className="px-4 py-3 text-left font-medium">官網</th>
                        <th className="px-4 py-3 text-left font-medium">業務</th>
                        <th className="px-4 py-3 text-left font-medium">狀態</th>
                        <th className="px-4 py-3 text-left font-medium">評分</th>
                        <th className="px-4 py-3 text-left font-medium cursor-pointer hover:text-primary" title="點擊依熱度排序">熱度 🔥</th>
                        <th className="px-4 py-3 text-left font-medium">含金量 🏆</th>
                        <th className="px-4 py-3 text-left font-medium">來源</th>
                        <th className="px-4 py-3 text-left font-medium w-16"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {pagedLeads.map(lead => {
                        const canAccess = isApprover(user) || user?.id === lead.assigned_to || lead.status === 'claiming'
                        return (
                        <tr
                          key={lead.id}
                          className={`transition-colors ${canAccess ? 'hover:bg-muted/30 cursor-pointer' : 'cursor-default opacity-80'} ${checked.has(lead.id) ? 'bg-indigo-50' : ''}`}
                          onClick={() => { if (canAccess) navigate(`/leads/${lead.id}`) }}
                        >
                          <td className="px-3 py-3" onClick={e => toggleCheck(lead.id, e)}>
                            <input type="checkbox" checked={checked.has(lead.id)} onChange={() => {}} className="rounded" />
                          </td>
                          <td className="px-4 py-3 font-medium">
                            {lead.company_name}
                            {!canAccess && <span className="ml-1 text-xs text-gray-400">🔒</span>}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {lead.contact_name || '—'}
                            {lead.title && <span className="text-xs ml-1">({lead.title})</span>}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{lead.email || '—'}</td>
                          <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                            {lead.phone ? (
                              <a
                                href={`tel:${lead.phone}`}
                                className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-2 py-1 rounded w-fit transition-colors"
                                title={`撥打 ${lead.phone}`}
                              >
                                <Phone className="w-3 h-3 shrink-0" />
                                {lead.phone}
                              </a>
                            ) : (
                              <span className="text-xs text-gray-300">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                            {lead.website ? (
                              <a
                                href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs text-blue-500 hover:underline max-w-[120px] truncate block"
                                title={lead.website}
                              >
                                {lead.website.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                              </a>
                            ) : <span className="text-xs text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">
                            {lead.assigned_user?.name
                              ? lead.assigned_user.name
                              : ragicContact(lead.notes)
                              ? <span className="text-gray-400" title="來自 Ragic 接洽人">{ragicContact(lead.notes)}</span>
                              : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-3"><StatusBadge status={lead.status} /></td>
                          <td className="px-4 py-3"><ScoreBadge score={lead.score} /></td>
                          <td className="px-4 py-3 text-xs">
                            {(() => {
                              const s = lead.engagement_score || 0
                              if (s >= 50) return <span title={`${s}分`}>🔥🔥🔥</span>
                              if (s >= 20) return <span title={`${s}分`}>🔥🔥</span>
                              if (s > 0) return <span title={`${s}分`}>🔥</span>
                              return <span className="text-gray-300" title="0分">⬜</span>
                            })()}
                          </td>
                          <td className="px-4 py-3">
                            {lead.enriched_score != null ? (
                              <div className="flex items-center gap-1">
                                <div className="w-16 bg-gray-100 rounded-full h-1.5">
                                  <div
                                    className={`h-1.5 rounded-full ${lead.enriched_score >= 70 ? 'bg-green-500' : lead.enriched_score >= 40 ? 'bg-yellow-400' : 'bg-gray-400'}`}
                                    style={{ width: `${lead.enriched_score}%` }}
                                  />
                                </div>
                                <span className="text-xs text-muted-foreground">{lead.enriched_score}</span>
                              </div>
                            ) : <span className="text-xs text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">{lead.source || '—'}</td>
                          <td className="px-4 py-3">
                            {user?.role !== 'sales' && (
                              <button
                                onClick={e => handleDelete(lead.id, e)}
                                className="text-muted-foreground hover:text-destructive transition-colors"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </td>
                        </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  <div className="border-t px-2">
                    <Pagination page={page} totalPages={totalPages} total={filteredLeads.length} onPage={setPage} />
                  </div>
                </div>
              </div>
            </>
          )}
          </div>{/* end flex-1 */}
        </div>
      )}

      {activeTab === 'CSV 匯入' && <CsvImportTab onImported={() => { loadLeads(); setActiveTab('手動管理'); }} />}
      {activeTab === '名單爬取' && <ScraperTab onImported={() => { loadLeads(); setActiveTab('手動管理'); }} />}
      {activeTab === '待審核' && <ApprovalTab onResolved={() => { loadLeads(); getLeadApprovalCount().then(r => setPendingCount(r.data?.count ?? 0)).catch(() => {}) }} />}

      {/* Create modal */}
      {showCreate && (
        <CreateLeadModal onClose={() => setShowCreate(false)} onCreated={loadLeads} />
      )}

    </div>
  )
}
