import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getLead, updateLead, updateLeadStatus, getActivities, createActivity,
  getGmailAuthUrl, sendEmail, generateDraft, scoreLead,
  getTemplates, scheduleEmail, getEmailOpenStatus, enrichCompany,
  enrichLushaPhone, enrichLushaStatus,
  getContacts, createContact, updateContact, deleteContact, setContactPrimary,
  getLeadTags, getTags, addLeadTags, removeLeadTag,
  getAttachments, uploadAttachment, downloadAttachment, deleteAttachment,
  getLeadCadences, getCalls, createCall, recalcEngagement,
  analyzeSignals, generateEmail, generateProposalEmail,
} from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { Lead, LeadStatus, Activity, EmailTemplate, Contact, Tag, Attachment, CadenceEnrollment, CallLog, CallOutcome, CALL_OUTCOME_LABELS, LEAD_STATUS_LABELS, LEAD_STATUS_COLORS, ACTIVITY_LABELS } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Mail, Sparkles, Star, Wand2, Clock, Plus, Trash2, Download, Upload, Tag as TagIcon, ExternalLink, Phone, Flame, Paperclip, X } from 'lucide-react'
import { format } from 'date-fns'

const CADENCE_STEP_ICONS: Record<string, string> = {
  email: '📧',
  call: '📞',
  linkedin: '🔗',
  sms: '💬',
}

function EngagementBadge({ score }: { score: number }) {
  if (score === 0) return <span className="text-xs text-muted-foreground">⬜ 無互動</span>
  if (score >= 50) return <span className="text-xs text-orange-600">🔥🔥🔥 高熱度 ({score})</span>
  if (score >= 20) return <span className="text-xs text-yellow-600">🔥🔥 中熱度 ({score})</span>
  return <span className="text-xs text-gray-500">🔥 低熱度 ({score})</span>
}

const PIPELINE = Object.keys(LEAD_STATUS_LABELS) as LeadStatus[]

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-muted-foreground">未評分</span>
  const color = score >= 80 ? 'bg-green-100 text-green-700' : score >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-sm font-medium ${color}`}>{score} 分</span>
}

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [lead, setLead] = useState<Lead | null>(null)
  const [form, setForm] = useState<Partial<Lead>>({})
  const [activities, setActivities] = useState<Activity[]>([])
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [openStatus, setOpenStatus] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [showEmail, setShowEmail] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [lushaEnriching, setLushaEnriching] = useState(false)
  const [lushaMsg, setLushaMsg] = useState('')
  const [scoring, setScoring] = useState(false)
  const [noteContent, setNoteContent] = useState('')
  const [activeTab, setActiveTab] = useState<'info' | 'contacts' | 'attachments' | 'cadence' | 'calls'>('info')

  // Signals / 含金量
  const [analyzingSignals, setAnalyzingSignals] = useState(false)
  const [showAiEmailModal, setShowAiEmailModal] = useState(false)
  const [capitalInput, setCapitalInput] = useState('')
  const [savingCapital, setSavingCapital] = useState(false)

  // Proposal
  const [showProposalModal, setShowProposalModal] = useState(false)
  const [proposalProduct, setProposalProduct] = useState('廣告投放')
  const [proposalTone, setProposalTone] = useState('professional')
  const [proposalResult, setProposalResult] = useState<{ subject: string; body: string; key_points: string[] } | null>(null)
  const [generatingProposal, setGeneratingProposal] = useState(false)

  // Cadence enrollments
  const [cadenceEnrollments, setCadenceEnrollments] = useState<CadenceEnrollment[]>([])

  // Call logs
  const [calls, setCalls] = useState<CallLog[]>([])
  const [showCallModal, setShowCallModal] = useState(false)
  const [callForm, setCallForm] = useState<{
    outcome: CallOutcome
    duration_seconds: number
    note: string
  }>({ outcome: 'answered', duration_seconds: 0, note: '' })
  const [savingCall, setSavingCall] = useState(false)

  // Contacts
  const [contacts, setContacts] = useState<Contact[]>([])
  const [showAddContact, setShowAddContact] = useState(false)
  const [contactForm, setContactForm] = useState<Partial<Contact>>({})
  const [editingContact, setEditingContact] = useState<Contact | null>(null)

  // Tags
  const [leadTags, setLeadTags] = useState<Tag[]>([])
  const [allTags, setAllTags] = useState<Tag[]>([])
  const [showTagPicker, setShowTagPicker] = useState(false)

  // Attachments
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [attachUploadTab, setAttachUploadTab] = useState<'file' | 'drive'>('file')
  const [driveUrl, setDriveUrl] = useState('')
  const [driveName, setDriveName] = useState('')
  const [driveSubmitting, setDriveSubmitting] = useState(false)

  // Email form
  const [emailTo, setEmailTo] = useState('')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')
  const [customerBackground, setCustomerBackground] = useState('')
  const [draftTemplate, setDraftTemplate] = useState('intro')
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [generatingDraft, setGeneratingDraft] = useState(false)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [scheduleMode, setScheduleMode] = useState(false)
  const [scheduledAt, setScheduledAt] = useState('')
  const [emailAttachments, setEmailAttachments] = useState<File[]>([])
  const emailFileInputRef = useRef<HTMLInputElement>(null)

  const loadLead = useCallback(async () => {
    if (!id) return
    const res = await getLead(id)
    setLead(res.data)
    setForm(res.data)
    setEmailTo(res.data.email || '')
    setCapitalInput(res.data.capital_amount || '')
  }, [id])

  const loadActivities = useCallback(async () => {
    if (!id) return
    const res = await getActivities(id)
    setActivities(Array.isArray(res.data) ? res.data : [])
  }, [id])

  const loadOpenStatus = useCallback(async () => {
    if (!id) return
    try {
      const res = await getEmailOpenStatus(id)
      const map: Record<string, string> = {}
      for (const o of res.data) {
        map[o.email_id] = o.opened_at
      }
      setOpenStatus(map)
    } catch {
      // ignore
    }
  }, [id])

  const loadContacts = useCallback(async () => {
    if (!id) return
    try { const res = await getContacts(id); setContacts(Array.isArray(res.data) ? res.data : []) } catch { /* ignore */ }
  }, [id])

  const loadTags = useCallback(async () => {
    if (!id) return
    try {
      const [leadRes, allRes] = await Promise.all([getLeadTags(id), getTags()])
      setLeadTags(leadRes.data)
      setAllTags(allRes.data)
    } catch { /* ignore */ }
  }, [id])

  const loadAttachments = useCallback(async () => {
    if (!id) return
    try { const res = await getAttachments(id); setAttachments(Array.isArray(res.data) ? res.data : []) } catch { /* ignore */ }
  }, [id])

  const loadCadenceEnrollments = useCallback(async () => {
    if (!id) return
    try { const res = await getLeadCadences(id); setCadenceEnrollments(Array.isArray(res.data) ? res.data : []) } catch { /* ignore */ }
  }, [id])

  const loadCalls = useCallback(async () => {
    if (!id) return
    try { const res = await getCalls(id); setCalls(Array.isArray(res.data) ? res.data : []) } catch { /* ignore */ }
  }, [id])

  useEffect(() => {
    loadLead()
    loadActivities()
    loadOpenStatus()
    loadContacts()
    loadTags()
    loadAttachments()
    loadCadenceEnrollments()
    loadCalls()
    getTemplates().then(r => setTemplates(Array.isArray(r.data) ? r.data : [])).catch(() => {})
  }, [loadLead, loadActivities, loadOpenStatus, loadContacts, loadTags, loadAttachments, loadCadenceEnrollments, loadCalls])

  const save = async () => {
    if (!id) return
    setSaving(true)
    try {
      await updateLead(id, form as Record<string, unknown>)
      await loadLead()
    } finally {
      setSaving(false)
    }
  }

  const changeStatus = async (status: LeadStatus) => {
    if (!id) return
    await updateLeadStatus(id, status)
    setForm(f => ({ ...f, status }))
    setLead(l => l ? { ...l, status } : l)
    await loadActivities()
  }

  const handleScore = async () => {
    if (!id) return
    setScoring(true)
    try {
      await scoreLead(id)
      await loadLead()
    } finally {
      setScoring(false)
    }
  }

  const handleLushaPhone = async () => {
    if (!id || !lead?.email) {
      alert('需要有 Email 才能用 Lusha 補電話')
      return
    }
    setLushaEnriching(true)
    setLushaMsg('啟動中...')
    try {
      const res = await enrichLushaPhone([id], 1)
      const jobId = res.data.job_id
      setLushaMsg('查詢中...')
      const poll = async () => {
        const s = await enrichLushaStatus(jobId)
        const { status, enriched, skipped, failed } = s.data
        if (status === 'done') {
          setLushaEnriching(false)
          setLushaMsg('')
          if (enriched > 0) {
            await loadLead()
            alert('✅ Lusha 補電話成功！')
          } else {
            alert(`Lusha 查無此人資料（查無資料 ${skipped} 筆${failed > 0 ? `，API 錯誤 ${failed} 筆` : ''}）`)
          }
        } else if (status === 'failed') {
          setLushaEnriching(false)
          setLushaMsg('')
          alert('❌ Lusha API 錯誤，請稍後再試')
        } else {
          setTimeout(poll, 5000)
        }
      }
      setTimeout(poll, 5000)
    } catch {
      setLushaEnriching(false)
      setLushaMsg('')
      alert('Lusha 補電話失敗，請稍後再試')
    }
  }

  const handleEnrich = async () => {
    if (!id || !lead) return
    setEnriching(true)
    try {
      const res = await enrichCompany(lead.company_name, id)
      const data = res.data
      setForm(f => ({
        ...f,
        industry: f.industry || data.industry || f.industry,
        city: f.city || data.city || f.city,
        company_size: f.company_size || data.company_size || f.company_size,
        email: f.email || data.scraped_email || f.email,
        phone: f.phone || data.scraped_phone || f.phone,
      }))
      await loadLead()

      const lines = [
        `✅ AI 補全完成`,
        `產業：${data.industry || '—'}`,
        `城市：${data.city || '—'}`,
        `規模：${data.company_size || '—'}`,
      ]
      if (data.scraped_email) lines.push(`📧 Email：${data.scraped_email}`)
      if (data.scraped_phone) lines.push(`📞 電話：${data.scraped_phone}`)
      if (data.contact_url) lines.push(`🔗 來源：${data.contact_url}`)
      if (!data.scraped_email && !data.scraped_phone && lead.website) {
        lines.push(`⚠️ 聯絡頁未找到 Email / 電話（可能需手動查詢）`)
      } else if (!lead.website) {
        lines.push(`ℹ️ 未設定官網，略過聯絡資料爬取`)
      }
      if (data.summary) lines.push(`\n${data.summary}`)
      alert(lines.join('\n'))
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'AI 補全失敗')
    } finally {
      setEnriching(false)
    }
  }

  const handleDraft = async () => {
    if (!id) return
    setGeneratingDraft(true)
    try {
      const res = await generateDraft(id, draftTemplate, customerBackground || undefined)
      setEmailSubject(res.data.subject)
      setEmailBody(res.data.body)
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'AI 草稿失敗')
    } finally {
      setGeneratingDraft(false)
    }
  }

  const handleSelectTemplate = (templateId: string) => {
    setSelectedTemplate(templateId)
    const tmpl = templates.find(t => t.id === templateId)
    if (tmpl && lead) {
      const replace = (str: string) => str
        .replace(/\{\{company_name\}\}/g, lead.company_name)
        .replace(/\{\{contact_name\}\}/g, lead.contact_name || '您好')
        .replace(/\{\{industry\}\}/g, lead.industry || '')
        .replace(/\{\{city\}\}/g, lead.city || '')
      setEmailSubject(replace(tmpl.subject))
      setEmailBody(replace(tmpl.body))
    }
  }

  const encodeEmailAttachments = async (files: File[]) => {
    return Promise.all(files.map(async (file) => {
      const buffer = await file.arrayBuffer()
      const bytes = new Uint8Array(buffer)
      let binary = ''
      for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
      return { filename: file.name, content: btoa(binary), mime_type: file.type || 'application/octet-stream' }
    }))
  }

  const handleSendEmail = async () => {
    if (!id) return
    setSendingEmail(true)
    try {
      if (scheduleMode && scheduledAt) {
        await scheduleEmail({
          lead_id: id,
          to_email: emailTo,
          subject: emailSubject,
          body: emailBody,
          scheduled_at: new Date(scheduledAt).toISOString(),
          template_id: selectedTemplate || undefined,
        })
        setShowEmail(false)
        setEmailAttachments([])
        alert('✅ 已排程發送')
      } else {
        const attachments = emailAttachments.length > 0 ? await encodeEmailAttachments(emailAttachments) : undefined
        await sendEmail({ lead_id: id, to: emailTo, subject: emailSubject, body: emailBody, attachments })
        setShowEmail(false)
        setEmailAttachments([])
        await loadActivities()
        alert('郵件已送出')
      }
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
    if (!id || !noteContent.trim()) return
    await createActivity(id, { type: 'call_note', content: noteContent })
    setNoteContent('')
    await loadActivities()
  }

  const handleSaveCapital = async () => {
    if (!id || !lead) return
    setSavingCapital(true)
    try {
      await updateLead(id, { capital_amount: capitalInput })
      const websiteUrl = lead.website || undefined
      if (websiteUrl || lead.email) {
        await analyzeSignals(id, websiteUrl)
      }
      await loadLead()
    } catch {
      alert('儲存失敗')
    } finally {
      setSavingCapital(false)
    }
  }

  const handleAnalyzeSignals = async () => {
    if (!id || !lead) return
    // 優先用 website，沒有就讓後端從 email domain 推測
    const websiteUrl = lead.website || undefined
    if (!websiteUrl && !lead.email) {
      alert('請先填入官網 URL 或 Email')
      return
    }
    setAnalyzingSignals(true)
    try {
      const res = await analyzeSignals(id, websiteUrl)
      await loadLead()
      if (res.data?.inferred_website) {
        // 後端從 email 推測出官網，已自動填入
      }
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '分析失敗')
    } finally {
      setAnalyzingSignals(false)
    }
  }

  const handleGenerateProposal = async () => {
    if (!id) return
    setGeneratingProposal(true)
    setProposalResult(null)
    try {
      const res = await generateProposalEmail({ lead_id: id, product: proposalProduct, tone: proposalTone })
      setProposalResult(res.data)
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '提案信生成失敗')
    } finally {
      setGeneratingProposal(false)
    }
  }

  if (!lead) return <div className="p-6 text-muted-foreground">載入中...</div>

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-4 md:px-6 py-4">
        <div className="flex items-center gap-4 mb-3">
          <button
            onClick={() => navigate('/leads')}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> 返回名單
          </button>
        </div>
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
          <div>
            <h1 className="text-xl md:text-2xl font-bold">{lead.company_name}</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              {lead.contact_name}
              {lead.title && ` · ${lead.title}`}
              {lead.email && <span className="hidden sm:inline"> · {lead.email}</span>}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <ScoreBadge score={lead.score} />
            <Button size="sm" variant="outline" onClick={handleScore} disabled={scoring}>
              <Star className="w-3.5 h-3.5 md:mr-1.5" />
              <span className="hidden md:inline">{scoring ? '評分中...' : '重新評分'}</span>
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowAiEmailModal(true)}>
              <Sparkles className="w-3.5 h-3.5 md:mr-1.5" />
              <span className="hidden md:inline">✨ AI 生成 Email</span>
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setShowProposalModal(true); setProposalResult(null) }}>
              <span className="md:mr-1.5">📋</span>
              <span className="hidden md:inline">生成提案信</span>
            </Button>
            <Button size="sm" onClick={() => setShowEmail(true)}>
              <Mail className="w-3.5 h-3.5 md:mr-1.5" />
              <span className="hidden md:inline">發信</span>
            </Button>
          </div>
        </div>

        {/* Status bar */}
        <div className="flex gap-2 mt-4 flex-wrap">
          {PIPELINE.map(s => (
            <button
              key={s}
              onClick={() => changeStatus(s)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                (form.status || lead.status) === s
                  ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                  : 'border-input bg-white hover:bg-muted text-muted-foreground'
              }`}
            >
              {LEAD_STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {/* Tags row */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {leadTags.map(tag => (
            <span
              key={tag.id}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-white cursor-pointer hover:opacity-80"
              style={{ backgroundColor: tag.color }}
              onClick={async () => { if (!id) return; await removeLeadTag(id, tag.id); await loadTags() }}
              title="點擊移除"
            >
              {tag.name} ×
            </span>
          ))}
          <button
            onClick={() => setShowTagPicker(t => !t)}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs text-muted-foreground border border-dashed hover:border-gray-400 transition-colors"
          >
            <TagIcon className="w-3 h-3" /> 加標籤
          </button>
          {showTagPicker && (
            <div className="flex gap-1 flex-wrap">
              {allTags.filter(t => !leadTags.find(lt => lt.id === t.id)).map(tag => (
                <button
                  key={tag.id}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs text-white font-medium hover:opacity-80 transition-opacity"
                  style={{ backgroundColor: tag.color }}
                  onClick={async () => {
                    if (!id) return
                    await addLeadTags(id, [tag.id])
                    await loadTags()
                    setShowTagPicker(false)
                  }}
                >
                  + {tag.name}
                </button>
              ))}
              {allTags.filter(t => !leadTags.find(lt => lt.id === t.id)).length === 0 && (
                <span className="text-xs text-muted-foreground">所有標籤已套用</span>
              )}
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 border-b -mb-px flex-wrap">
          {[
            { key: 'info', label: '基本資料' },
            { key: 'contacts', label: `聯絡人 (${contacts.length})` },
            { key: 'attachments', label: `附件 (${attachments.length})` },
            { key: 'cadence', label: `Cadence (${cadenceEnrollments.length})` },
            { key: 'calls', label: `通話記錄 (${calls.length})` },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as typeof activeTab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                activeTab === key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab: Contacts */}
      {activeTab === 'contacts' && (
        <div className="p-6 max-w-4xl">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">聯絡人</h2>
            <Button size="sm" onClick={() => { setContactForm({}); setEditingContact(null); setShowAddContact(true) }}>
              <Plus className="w-3.5 h-3.5 mr-1" /> 新增聯絡人
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {contacts.length === 0 ? (
              <p className="text-sm text-muted-foreground col-span-2">尚無聯絡人記錄</p>
            ) : contacts.map(c => (
              <div key={c.id} className="bg-white border rounded-xl p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      {c.is_primary && <span className="text-yellow-500 text-sm">⭐</span>}
                    </div>
                    {c.title && <p className="text-xs text-muted-foreground">{c.title}</p>}
                    <div className="mt-2 space-y-1 text-sm">
                      {c.email && <p><span className="text-muted-foreground text-xs">Email：</span>{c.email}</p>}
                      {c.phone && <p><span className="text-muted-foreground text-xs">電話：</span>{c.phone}</p>}
                      {c.linkedin && (
                        <p>
                          <span className="text-muted-foreground text-xs">LinkedIn：</span>
                          <a href={c.linkedin} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline text-xs truncate">{c.linkedin}</a>
                        </p>
                      )}
                    </div>
                    {c.notes && <p className="text-xs text-gray-500 mt-2">{c.notes}</p>}
                  </div>
                  <div className="flex flex-col gap-1">
                    {!c.is_primary && (
                      <Button variant="outline" size="sm" className="text-xs h-7 px-2" onClick={async () => {
                        await setContactPrimary(c.id); await loadContacts()
                      }}>設為主要</Button>
                    )}
                    <Button variant="outline" size="sm" className="text-xs h-7 px-2" onClick={() => {
                      setContactForm(c); setEditingContact(c); setShowAddContact(true)
                    }}>編輯</Button>
                    <Button variant="outline" size="sm" className="text-xs h-7 px-2 text-red-500" onClick={async () => {
                      if (!confirm('確定刪除？')) return
                      await deleteContact(c.id); await loadContacts()
                    }}>
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Dialog open={showAddContact} onOpenChange={setShowAddContact}>
            <DialogContent>
              <DialogHeader><DialogTitle>{editingContact ? '編輯聯絡人' : '新增聯絡人'}</DialogTitle></DialogHeader>
              <div className="space-y-3">
                {[
                  { label: '姓名 *', key: 'name', type: 'text' },
                  { label: '職稱', key: 'title', type: 'text' },
                  { label: 'Email', key: 'email', type: 'email' },
                  { label: '電話', key: 'phone', type: 'tel' },
                  { label: 'LinkedIn', key: 'linkedin', type: 'url' },
                ].map(({ label, key, type }) => (
                  <div key={key}>
                    <Label className="text-xs">{label}</Label>
                    <Input
                      type={type}
                      value={(contactForm as Record<string, unknown>)[key] as string || ''}
                      onChange={e => setContactForm(f => ({ ...f, [key]: e.target.value }))}
                      className="mt-0.5"
                    />
                  </div>
                ))}
                <div>
                  <Label className="text-xs">備注</Label>
                  <Textarea
                    value={contactForm.notes || ''}
                    onChange={e => setContactForm(f => ({ ...f, notes: e.target.value }))}
                    rows={2}
                    className="mt-0.5"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={contactForm.is_primary || false}
                    onChange={e => setContactForm(f => ({ ...f, is_primary: e.target.checked }))}
                  />
                  設為主要聯絡人
                </label>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowAddContact(false)}>取消</Button>
                  <Button onClick={async () => {
                    if (!id || !contactForm.name?.trim()) return
                    if (editingContact) {
                      await updateContact(editingContact.id, contactForm as Record<string, unknown>)
                    } else {
                      await createContact(id, contactForm as Record<string, unknown>)
                    }
                    setShowAddContact(false)
                    await loadContacts()
                  }}>
                    {editingContact ? '更新' : '新增'}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {/* Tab: Attachments */}
      {activeTab === 'attachments' && (
        <div className="p-6 max-w-4xl">
          <h2 className="font-semibold mb-4">附件</h2>

          {/* Upload mode tabs */}
          <div className="flex border-b mb-4">
            <button
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${attachUploadTab === 'file' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              onClick={() => setAttachUploadTab('file')}
            >
              <Upload className="w-3.5 h-3.5 inline mr-1" /> 上傳檔案
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${attachUploadTab === 'drive' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              onClick={() => setAttachUploadTab('drive')}
            >
              <ExternalLink className="w-3.5 h-3.5 inline mr-1" /> Google Drive 連結
            </button>
          </div>

          {/* File upload tab */}
          {attachUploadTab === 'file' && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (!file || !id) return
                  const reader = new FileReader()
                  reader.onload = async () => {
                    const base64 = (reader.result as string).split(',')[1]
                    try {
                      await uploadAttachment(id, { filename: file.name, file_data: base64, file_type: file.type })
                      await loadAttachments()
                    } catch (err: unknown) {
                      const e = err as { response?: { data?: { detail?: string } } }
                      alert(e?.response?.data?.detail || '上傳失敗')
                    }
                  }
                  reader.readAsDataURL(file)
                  e.target.value = ''
                }}
              />
              <div
                className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center mb-4 hover:border-gray-400 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={async (e) => {
                  e.preventDefault()
                  const file = e.dataTransfer.files?.[0]
                  if (!file || !id) return
                  const reader = new FileReader()
                  reader.onload = async () => {
                    const base64 = (reader.result as string).split(',')[1]
                    try {
                      await uploadAttachment(id, { filename: file.name, file_data: base64, file_type: file.type })
                      await loadAttachments()
                    } catch (err: unknown) {
                      const e = err as { response?: { data?: { detail?: string } } }
                      alert(e?.response?.data?.detail || '上傳失敗')
                    }
                  }
                  reader.readAsDataURL(file)
                }}
              >
                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p className="text-sm text-muted-foreground">拖拉或點擊上傳（最大 5MB）</p>
              </div>
            </>
          )}

          {/* Google Drive link tab */}
          {attachUploadTab === 'drive' && (
            <div className="border rounded-xl p-6 mb-4 bg-gray-50">
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">Drive 連結 *</label>
                  <input
                    type="url"
                    value={driveUrl}
                    onChange={(e) => setDriveUrl(e.target.value)}
                    placeholder="https://drive.google.com/file/d/..."
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-1 block">檔案名稱（選填）</label>
                  <input
                    type="text"
                    value={driveName}
                    onChange={(e) => setDriveName(e.target.value)}
                    placeholder="例如：提案簡報 2026"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <Button
                  size="sm"
                  disabled={!driveUrl || driveSubmitting}
                  onClick={async () => {
                    if (!driveUrl || !id) return
                    if (!driveUrl.startsWith('https://drive.google.com')) {
                      alert('只接受 drive.google.com 的連結')
                      return
                    }
                    setDriveSubmitting(true)
                    try {
                      await uploadAttachment(id, { drive_url: driveUrl, drive_name: driveName || undefined })
                      await loadAttachments()
                      setDriveUrl('')
                      setDriveName('')
                    } catch (err: unknown) {
                      const e = err as { response?: { data?: { detail?: string } } }
                      alert(e?.response?.data?.detail || '新增失敗')
                    } finally {
                      setDriveSubmitting(false)
                    }
                  }}
                >
                  <ExternalLink className="w-3.5 h-3.5 mr-1" />
                  {driveSubmitting ? '新增中...' : '新增 Drive 連結'}
                </Button>
              </div>
            </div>
          )}

          {/* Attachment list */}
          <div className="space-y-2">
            {attachments.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">尚無附件</p>
            ) : attachments.map(att => (
              <div key={att.id} className="flex items-center justify-between bg-white border rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 min-w-0">
                  {att.is_drive_link
                    ? <ExternalLink className="w-4 h-4 text-blue-500 flex-shrink-0" />
                    : <Download className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  }
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{att.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {att.file_size ? `${(att.file_size / 1024).toFixed(1)} KB · ` : ''}
                      {new Date(att.created_at).toLocaleString('zh-TW')}
                    </p>
                  </div>
                </div>
                <div className="flex gap-1 flex-shrink-0 ml-2">
                  {att.is_drive_link ? (
                    <Button variant="outline" size="sm" asChild>
                      <a href={att.drive_url!} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="w-3.5 h-3.5 mr-1" /> 在 Drive 開啟
                      </a>
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={async () => {
                      const res = await downloadAttachment(att.id)
                      const url = URL.createObjectURL(new Blob([res.data]))
                      const a = document.createElement('a')
                      a.href = url
                      a.download = att.filename
                      a.click()
                      URL.revokeObjectURL(url)
                    }}>
                      <Download className="w-3.5 h-3.5" />
                    </Button>
                  )}
                  <Button variant="outline" size="sm" className="text-red-500" onClick={async () => {
                    if (!confirm('確定刪除此附件？')) return
                    await deleteAttachment(att.id)
                    await loadAttachments()
                  }}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Cadence */}
      {activeTab === 'cadence' && (
        <div className="p-6 max-w-4xl">
          <h2 className="font-semibold mb-4">Cadence 波段進度</h2>
          {cadenceEnrollments.length === 0 ? (
            <p className="text-sm text-muted-foreground">此名單尚未加入任何 Cadence 波段</p>
          ) : (
            <div className="space-y-4">
              {cadenceEnrollments.map(e => {
                const progress = e.total_steps > 0
                  ? Math.round((e.current_step / e.total_steps) * 100)
                  : 0
                return (
                  <div key={e.id} className="bg-white border rounded-xl p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="font-medium">{e.cadence_name}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          e.status === 'active' ? 'bg-green-100 text-green-700' :
                          e.status === 'completed' ? 'bg-blue-100 text-blue-700' :
                          'bg-yellow-100 text-yellow-700'
                        }`}>{e.status}</span>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">{e.current_step}/{e.total_steps} 步驟</p>
                        {e.next_action_at && e.status === 'active' && (
                          <p className="text-xs text-orange-500 mt-0.5">
                            下次：{new Date(e.next_action_at).toLocaleDateString('zh-TW')}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2 mb-3">
                      <div
                        className="bg-primary h-2 rounded-full transition-all"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    {e.step_logs.length > 0 && (
                      <div className="space-y-1">
                        {e.step_logs.map(log => (
                          <div key={log.id} className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{CADENCE_STEP_ICONS[log.step_type] || '📋'}</span>
                            <span className={log.status === 'done' ? 'text-green-600' : 'text-yellow-600'}>
                              {log.status === 'done' ? '✓' : '→'} Step {log.step_index + 1}
                            </span>
                            {log.executed_at && (
                              <span>{new Date(log.executed_at).toLocaleDateString('zh-TW')}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Calls */}
      {activeTab === 'calls' && (
        <div className="p-6 max-w-4xl">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">通話記錄</h2>
            <Button size="sm" onClick={() => setShowCallModal(true)}>
              <Phone className="w-3.5 h-3.5 mr-1.5" /> 新增通話
            </Button>
          </div>
          <div className="space-y-3">
            {calls.length === 0 ? (
              <p className="text-sm text-muted-foreground">尚無通話記錄</p>
            ) : calls.map(c => (
              <div key={c.id} className="bg-white border rounded-xl p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-sm font-medium ${
                        c.outcome === 'answered' ? 'text-green-600' : 'text-gray-700'
                      }`}>
                        {c.outcome === 'answered' ? '✓' : '✗'}{' '}
                        {c.outcome ? CALL_OUTCOME_LABELS[c.outcome] : ''}
                      </span>
                      {c.duration_seconds && c.duration_seconds > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {Math.floor(c.duration_seconds / 60)}分{c.duration_seconds % 60}秒
                        </span>
                      )}
                    </div>
                    {c.note && <p className="text-sm text-gray-600">{c.note}</p>}
                  </div>
                  <div className="text-right text-xs text-muted-foreground">
                    <p>{new Date(c.called_at).toLocaleString('zh-TW')}</p>
                    {c.caller_name && <p>{c.caller_name}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Dialog open={showCallModal} onOpenChange={setShowCallModal}>
            <DialogContent>
              <DialogHeader><DialogTitle>新增通話記錄</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div>
                  <Label>通話結果</Label>
                  <Select value={callForm.outcome} onValueChange={v => setCallForm(f => ({ ...f, outcome: v as CallOutcome }))}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(CALL_OUTCOME_LABELS).map(([v, l]) => (
                        <SelectItem key={v} value={v}>{l}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>時長（秒）</Label>
                  <Input
                    type="number"
                    min={0}
                    value={callForm.duration_seconds}
                    onChange={e => setCallForm(f => ({ ...f, duration_seconds: parseInt(e.target.value) || 0 }))}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>備注</Label>
                  <Textarea
                    value={callForm.note}
                    onChange={e => setCallForm(f => ({ ...f, note: e.target.value }))}
                    rows={3}
                    className="mt-1"
                    placeholder="通話內容摘要..."
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCallModal(false)}>取消</Button>
                  <Button
                    disabled={savingCall}
                    onClick={async () => {
                      if (!id) return
                      setSavingCall(true)
                      try {
                        await createCall(id, callForm as Record<string, unknown>)
                        setShowCallModal(false)
                        setCallForm({ outcome: 'answered', duration_seconds: 0, note: '' })
                        await loadCalls()
                        await loadLead()
                      } finally {
                        setSavingCall(false)
                      }
                    }}
                  >
                    {savingCall ? '儲存中...' : '儲存'}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {/* Body */}
      {activeTab === 'info' && <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 md:gap-6 p-3 md:p-6">
        {/* Left: Edit form */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-sm">基本資料</h2>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={handleEnrich} disabled={enriching}>
                  <Wand2 className="w-3.5 h-3.5 mr-1.5" />
                  {enriching ? 'AI 補全中...' : 'AI 補全資訊'}
                </Button>
                <Button size="sm" variant="outline" onClick={handleLushaPhone} disabled={lushaEnriching || !lead?.email}>
                  📞 {lushaEnriching ? (lushaMsg || '查詢中...') : 'Lusha 補電話'}
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: '公司名稱', key: 'company_name' },
                { label: '統編', key: 'tax_id' },
                { label: '資本總額(元)', key: 'capital_amount' },
                { label: '聯絡人', key: 'contact_name' },
                { label: '部門', key: 'department' },
                { label: '職稱', key: 'title' },
                { label: 'Email', key: 'email' },
                { label: '電話', key: 'phone' },
                { label: '公司網址', key: 'website' },
                { label: '產業', key: 'industry' },
                { label: '城市', key: 'city' },
                { label: '公司規模', key: 'company_size' },
                { label: '來源', key: 'source' },
              ].map(({ label, key }) => (
                <div key={key} className={key === 'company_name' || key === 'website' ? 'col-span-2' : ''}>
                  <Label className="text-xs">{label}</Label>
                  <Input
                    value={(form as Record<string, unknown>)[key] as string || ''}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                    className="h-8 text-sm mt-0.5"
                  />
                </div>
              ))}
              <div className="col-span-2">
                <Label className="text-xs">備注</Label>
                <Textarea
                  value={form.notes || ''}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  rows={3}
                  className="text-sm mt-0.5"
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={save} disabled={saving}>
                {saving ? '儲存中...' : '儲存變更'}
              </Button>
            </div>
          </div>

          {/* Score details */}
          {lead.score !== null && (
            <div className="bg-white border rounded-xl p-5">
              <h2 className="font-semibold text-sm mb-2">AI 評分</h2>
              <div className="flex items-center gap-3 mb-2">
                <ScoreBadge score={lead.score} />
                <span className="text-xs text-muted-foreground">
                  {lead.score >= 80 ? '🔥 高潛力' : lead.score >= 50 ? '⚡ 有機會' : '❄️ 需培養'}
                </span>
              </div>
              {lead.score_reason && (
                <p className="text-sm text-gray-600 whitespace-pre-wrap">{lead.score_reason}</p>
              )}
            </div>
          )}

          {/* 含金量分析卡片 */}
          <div className="bg-white border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm">🏆 含金量分析</h2>
              <Button size="sm" variant="outline" onClick={handleAnalyzeSignals} disabled={analyzingSignals}>
                🔍 {analyzingSignals ? '分析中...' : '分析含金量'}
              </Button>
            </div>
            {lead.enriched_score != null ? (
              <div className="space-y-4 text-xs">
                {/* 分數 */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-muted-foreground">含金量分數</span>
                    <span className="font-bold text-sm">{lead.enriched_score}/100</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div className={`h-2 rounded-full transition-all ${lead.enriched_score >= 70 ? 'bg-green-500' : lead.enriched_score >= 40 ? 'bg-yellow-400' : 'bg-gray-400'}`}
                      style={{ width: `${lead.enriched_score}%` }} />
                  </div>
                </div>

                {/* 技術追蹤 */}
                {lead.tech_signals && (
                  <div>
                    <p className="font-medium text-muted-foreground mb-1.5">🔧 技術追蹤</p>
                    <div className="space-y-1 pl-1">
                      <div className="flex gap-2 flex-wrap">
                        {lead.tech_signals.gtm && <span className="bg-green-50 text-green-700 px-1.5 py-0.5 rounded">GTM {lead.tech_signals.gtm_ids?.length > 0 ? `(${lead.tech_signals.gtm_ids[0]})` : '✓'}</span>}
                        {lead.tech_signals.meta_pixel && <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">Meta Pixel {lead.tech_signals.meta_pixel_ids?.length > 0 ? `(${lead.tech_signals.meta_pixel_ids[0]})` : '✓'}</span>}
                        {lead.tech_signals.ga4 && <span className="bg-orange-50 text-orange-700 px-1.5 py-0.5 rounded">GA4 {lead.tech_signals.ga4_ids?.length > 0 ? `(${lead.tech_signals.ga4_ids[0]})` : '✓'}</span>}
                        {lead.tech_signals.remarketing && <span className="bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded">再行銷 ✓</span>}
                        {lead.tech_signals.other_trackers?.map((t: string) => (
                          <span key={t} className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{t}</span>
                        ))}
                      </div>
                      {lead.tech_signals.meta_completeness && (
                        <div className="text-muted-foreground">SEO Meta 完整度：<span className="font-medium text-gray-700">{lead.tech_signals.meta_completeness}</span>
                          {lead.tech_signals.meta_tags_present?.length > 0 && <span className="text-gray-400"> ({lead.tech_signals.meta_tags_present.join(', ')})</span>}
                        </div>
                      )}
                      {lead.tech_signals.seo_keyword_count > 0 && (
                        <div className="text-muted-foreground">Keywords：<span className="font-medium text-gray-700">{lead.tech_signals.seo_keyword_count} 個</span>
                          {lead.tech_signals.seo_keywords?.length > 0 && <span className="text-gray-400"> ({lead.tech_signals.seo_keywords.slice(0,5).join(', ')})</span>}
                        </div>
                      )}
                      {lead.tech_signals.schema_types?.length > 0 && (
                        <div className="text-muted-foreground">結構化資料：<span className="font-medium text-gray-700">{lead.tech_signals.schema_types.join(', ')}</span></div>
                      )}
                    </div>
                  </div>
                )}

                {/* 廣告投放 */}
                {lead.ad_signals && (
                  <div>
                    <p className="font-medium text-muted-foreground mb-1.5">💰 廣告投放</p>
                    <div className="space-y-1 pl-1">
                      {/* Meta Pixel */}
                      {lead.ad_signals.meta?.has_pixel ? (
                        <div>
                          <span className="text-green-700 font-medium">✅ Meta Pixel 已安裝</span>
                          {lead.ad_signals.meta.pixel_id && <span className="text-gray-400 ml-1">({lead.ad_signals.meta.pixel_id})</span>}
                          {lead.ad_signals.meta.pixel_events?.length > 0 && (
                            <div className="text-muted-foreground mt-0.5 flex gap-1 flex-wrap">
                              {lead.ad_signals.meta.pixel_events.map((e: any) => (
                                <span key={e.event} className="bg-blue-50 text-blue-700 px-1 rounded">{e.label}</span>
                              ))}
                            </div>
                          )}
                          {lead.ad_signals.meta.is_retargeting && <div className="text-purple-600">再行銷受眾已設定 ✓</div>}
                        </div>
                      ) : <span className="text-gray-400">❌ 未偵測到 Meta Pixel</span>}
                      {/* Google Ads */}
                      {lead.ad_signals.google_ads?.has_ads ? (
                        <div>
                          <span className="text-green-700 font-medium">✅ Google Ads 追蹤碼</span>
                          {lead.ad_signals.google_ads.ad_types?.length > 0 && (
                            <div className="flex gap-1 flex-wrap mt-0.5">
                              {lead.ad_signals.google_ads.ad_types.map((t: string) => (
                                <span key={t} className="bg-yellow-50 text-yellow-700 px-1 rounded">{t}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : <span className="text-gray-400">❌ 未偵測到 Google Ads</span>}
                    </div>
                  </div>
                )}

                {/* 積極營運 */}
                {lead.ops_signals && (
                  <div>
                    <p className="font-medium text-muted-foreground mb-1.5">🚀 積極營運</p>
                    <div className="space-y-1 pl-1">
                      {lead.ops_signals.promotion_types?.length > 0
                        ? <div><span className="text-green-700">✅ 促銷活動：</span><span className="text-gray-600">{lead.ops_signals.promotion_types.join('、')}</span></div>
                        : <span className="text-gray-400">❌ 無促銷活動</span>}
                      <div className="flex gap-3">
                        <span>{lead.ops_signals.product_links_count > 0 ? '✅' : '❌'} 商品連結 <span className="font-medium">{lead.ops_signals.product_links_count ?? 0}</span> 個</span>
                        <span>{lead.ops_signals.category_links_count > 0 ? '✅' : '❌'} 分類 <span className="font-medium">{lead.ops_signals.category_links_count ?? 0}</span> 個</span>
                      </div>
                      <div className="flex gap-3">
                        <span>{lead.ops_signals.video_count > 0 ? '✅' : '❌'} 影片 <span className="font-medium">{lead.ops_signals.video_count ?? 0}</span> 個</span>
                        <span>{lead.ops_signals.blog_links_count > 0 ? '✅' : '❌'} 文章連結 <span className="font-medium">{lead.ops_signals.blog_links_count ?? 0}</span> 個</span>
                      </div>
                      {lead.ops_signals.cart_features?.length > 0 && (
                        <div><span className="text-green-700">✅ 電商功能：</span><span className="text-gray-600">{lead.ops_signals.cart_features.join('、')}</span></div>
                      )}
                    </div>
                  </div>
                )}

                {/* 市場體量 */}
                {lead.market_signals && (
                  <div>
                    <p className="font-medium text-muted-foreground mb-1.5">📊 市場體量</p>
                    <div className="space-y-1 pl-1">
                      {/* 社群粉絲數 */}
                      {lead.market_signals.followers && (
                        <div className="flex gap-3 flex-wrap">
                          {lead.market_signals.followers.facebook?.count != null && (
                            <span>FB <span className="font-medium text-blue-700">{lead.market_signals.followers.facebook.count.toLocaleString()}</span> 追蹤</span>
                          )}
                          {lead.market_signals.followers.instagram?.count != null && (
                            <span>IG <span className="font-medium text-pink-700">{lead.market_signals.followers.instagram.count.toLocaleString()}</span> 追蹤</span>
                          )}
                          {lead.market_signals.followers.youtube?.count != null && (
                            <span>YT <span className="font-medium text-red-700">{lead.market_signals.followers.youtube.count.toLocaleString()}</span> 訂閱</span>
                          )}
                        </div>
                      )}
                      {/* 社群平台 */}
                      <div className="flex gap-2 flex-wrap">
                        {lead.market_signals.has_facebook && <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">Facebook</span>}
                        {lead.market_signals.has_instagram && <span className="bg-pink-50 text-pink-700 px-1.5 py-0.5 rounded">Instagram</span>}
                        {lead.market_signals.has_youtube && <span className="bg-red-50 text-red-700 px-1.5 py-0.5 rounded">YouTube</span>}
                        {lead.market_signals.has_linkedin && <span className="bg-blue-50 text-blue-800 px-1.5 py-0.5 rounded">LinkedIn</span>}
                        {lead.market_signals.has_line && <span className="bg-green-50 text-green-700 px-1.5 py-0.5 rounded">LINE</span>}
                        {lead.market_signals.has_threads && <span className="bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">Threads</span>}
                      </div>
                      <div className="flex gap-3 text-muted-foreground">
                        {lead.market_signals.og_tags_count > 0 && <span>OG Tags：<span className="text-gray-700 font-medium">{lead.market_signals.og_tags_count}</span> 個</span>}
                        {lead.market_signals.sitemap_url_count > 0 && <span>Sitemap：<span className="text-gray-700 font-medium">{lead.market_signals.sitemap_url_count}</span> 頁</span>}
                      </div>
                    </div>
                  </div>
                )}

                {/* 口袋深度 */}
                <div>
                  <p className="font-medium text-muted-foreground mb-1.5">
                    💼 口袋深度
                    <a
                      href={`https://findbiz.nat.gov.tw/fts/query/QueryBar/queryInit.do?qryCond=${encodeURIComponent(lead.tax_id || lead.company_name)}&infoType=D`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 text-xs text-blue-500 hover:text-blue-700 underline font-normal"
                    >
                      🔍 工商登記查詢
                    </a>
                  </p>
                  {/* 手動填入資本額 */}
                  <div className="flex items-center gap-1.5 mb-2">
                    <Input
                      value={capitalInput}
                      onChange={e => setCapitalInput(e.target.value)}
                      placeholder="資本額，例：500萬 或 5000000"
                      className="h-7 text-xs flex-1"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs px-2 whitespace-nowrap"
                      disabled={savingCapital}
                      onClick={handleSaveCapital}
                    >
                      {savingCapital ? '計算中...' : '儲存並重新計分'}
                    </Button>
                  </div>
                  {lead.wallet_signals && (
                    <div className="space-y-1 pl-1">
                      {lead.wallet_signals.company_name_matched && lead.wallet_signals.company_name_matched !== lead.company_name && (
                        <div className="text-xs text-gray-400">登記名稱：{lead.wallet_signals.company_name_matched}</div>
                      )}
                      {(lead.wallet_signals.company_capital != null || lead.wallet_signals.company_capital_tw) ? (
                        <div>
                          <span className="text-green-700 font-medium">資本額：</span>
                          <span className="font-bold text-gray-800">{lead.wallet_signals.company_capital_tw || `${(lead.wallet_signals.company_capital / 10000).toLocaleString()} 萬元`}</span>
                          {lead.wallet_signals.company_status && <span className="ml-2 text-gray-500">({lead.wallet_signals.company_status})</span>}
                        </div>
                      ) : (lead.capital_amount ? (
                        <div>
                          <span className="text-green-700 font-medium">資本額：</span>
                          <span className="font-bold text-gray-800">{lead.capital_amount}</span>
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">工商登記查無資本額，可手動填入</span>
                      ))}
                      {(lead.wallet_signals.company_representative || lead.representative_name) && (
                        <div className="text-muted-foreground">代表人：<span className="text-gray-700">{lead.wallet_signals.company_representative || lead.representative_name}</span></div>
                      )}
                      {lead.wallet_signals.established_date && (
                        <div className="text-muted-foreground">設立日期：<span className="text-gray-700">{lead.wallet_signals.established_date}</span></div>
                      )}
                      {lead.wallet_signals.company_status && !lead.wallet_signals.company_capital_tw && !lead.wallet_signals.company_capital && (
                        <div className="text-muted-foreground">公司狀態：<span className="text-gray-700">{lead.wallet_signals.company_status}</span></div>
                      )}
                      {lead.wallet_signals.business_items?.length > 0 && (
                        <div className="text-muted-foreground text-xs">營業項目：{lead.wallet_signals.business_items.slice(0, 3).join('、')}</div>
                      )}
                      {lead.wallet_signals.ad_platform_count > 0 && (
                        <div>
                          <span className="text-green-700">廣告平台數：</span>
                          <span className="font-bold text-gray-800">{lead.wallet_signals.ad_platform_count}</span> 個
                          <span className="text-gray-400 ml-1">({lead.wallet_signals.ad_platforms_found?.join(', ')})</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">尚未分析，點擊按鈕開始掃描官網</p>
            )}
          </div>

          {/* Intent Score visualization */}
          {lead.score_reason && lead.score_reason.includes('意圖:') && (() => {
            const intentPart = lead.score_reason.split('｜意圖:')[1] || ''
            const items = intentPart.split('、').filter(Boolean)
            // Extract total intent score from breakdowns
            const totalIntent = items.reduce((sum, item) => {
              const m = item.match(/\+(\d+)\)/)
              return sum + (m ? parseInt(m[1]) : 0)
            }, 0)
            const pct = Math.min(100, (totalIntent / 50) * 100)
            return (
              <div className="bg-white border rounded-xl p-5">
                <h2 className="font-semibold text-sm mb-3 flex items-center gap-2">
                  <Flame className="w-4 h-4 text-orange-500" /> Intent Score
                  {totalIntent >= 30 && <span className="text-xs px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded-full">MQL ✓</span>}
                </h2>
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${pct >= 60 ? 'bg-orange-500' : pct >= 40 ? 'bg-yellow-400' : 'bg-blue-400'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold tabular-nums">{totalIntent}</span>
                </div>
                <div className="space-y-1 mt-2">
                  {items.map((item, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-400 flex-shrink-0" />
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            )
          })()}
        </div>

        {/* Right: Timeline + email history */}
        <div className="lg:col-span-3 space-y-4">
          {/* Add note */}
          <div className="bg-white border rounded-xl p-5">
            <h2 className="font-semibold text-sm mb-3">新增記錄</h2>
            <div className="flex gap-2">
              <Textarea
                placeholder="輸入通話記錄、會議備注..."
                value={noteContent}
                onChange={e => setNoteContent(e.target.value)}
                rows={2}
                className="text-sm flex-1"
              />
              <Button size="sm" onClick={addNote} className="self-end">新增</Button>
            </div>
          </div>

          {/* Activity timeline */}
          <div className="bg-white border rounded-xl p-5">
            <h2 className="font-semibold text-sm mb-4">活動記錄 ({activities.length})</h2>
            {activities.length === 0 ? (
              <p className="text-sm text-muted-foreground">尚無活動記錄</p>
            ) : (
              <div className="space-y-4">
                {activities.map(act => {
                  // Check if this is an email activity and look for open tracking
                  const isEmail = act.type === 'email_sent'
                  const openEntry = isEmail
                    ? Object.entries(openStatus).find(([k]) => k.startsWith(lead.id))
                    : null

                  return (
                    <div key={act.id} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                          act.type === 'email_sent' ? 'bg-blue-500' :
                          act.type === 'status_change' ? 'bg-purple-500' :
                          act.type === 'meeting_note' ? 'bg-green-500' :
                          'bg-gray-400'
                        }`} />
                        <div className="w-px flex-1 bg-gray-100 mt-1" />
                      </div>
                      <div className="pb-4 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-medium">{ACTIVITY_LABELS[act.type]}</span>
                          <span className="text-xs text-muted-foreground">
                            {new Date(act.created_at).toLocaleString('zh-TW')}
                          </span>
                          {act.creator && (
                            <span className="text-xs text-muted-foreground">— {act.creator.name}</span>
                          )}
                          {isEmail && (
                            <span className={`text-xs px-1.5 py-0.5 rounded ${
                              openEntry ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                            }`}>
                              {openEntry
                                ? `✓ 已開信 ${format(new Date(openEntry[1]), 'MM/dd HH:mm')}`
                                : '未開信'}
                            </span>
                          )}
                        </div>
                        {act.content && (
                          <p className="text-sm text-gray-700 mt-1 whitespace-pre-wrap">{act.content}</p>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      }

      {/* Email Modal */}
      <Dialog open={showEmail} onOpenChange={v => { setShowEmail(v); if (!v) setEmailAttachments([]) }}>
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>發送郵件</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>收件人</Label>
              <Input value={emailTo} onChange={e => setEmailTo(e.target.value)} className="mt-1" />
            </div>

            {/* Template picker */}
            {templates.length > 0 && (
              <div>
                <Label>選用模板</Label>
                <Select value={selectedTemplate} onValueChange={handleSelectTemplate}>
                  <SelectTrigger className="mt-1"><SelectValue placeholder="選擇模板（選填）" /></SelectTrigger>
                  <SelectContent>
                    {templates.map(t => (
                      <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* 客戶背景資訊 */}
            <div>
              <Label className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                客戶官網／背景資訊
                <span className="text-xs text-muted-foreground font-normal">（貼上官網內容或背景說明，AI 會據此客製化信件）</span>
              </Label>
              <Textarea
                value={customerBackground}
                onChange={e => setCustomerBackground(e.target.value)}
                placeholder="貼上客戶官網文字、產品介紹、公司簡介…AI 會根據這些資訊撰寫更有針對性的信件"
                rows={4}
                className="mt-1 text-sm"
              />
            </div>

            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <Label>AI 草稿類型</Label>
                <Select value={draftTemplate} onValueChange={setDraftTemplate}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
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
              <Input value={emailSubject} onChange={e => setEmailSubject(e.target.value)} className="mt-1" />
            </div>
            <div>
              <Label>內文</Label>
              <Textarea value={emailBody} onChange={e => setEmailBody(e.target.value)} rows={8} className="mt-1" />
            </div>

            {/* Attachments */}
            <div>
              <Label className="flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5" /> 附件
              </Label>
              <input
                ref={emailFileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={e => {
                  if (e.target.files) {
                    setEmailAttachments(prev => [...prev, ...Array.from(e.target.files!)])
                    e.target.value = ''
                  }
                }}
              />
              <button
                type="button"
                onClick={() => emailFileInputRef.current?.click()}
                className="mt-1 w-full border-2 border-dashed border-muted-foreground/30 rounded-md py-2 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors"
              >
                點擊選擇檔案（可多選）
              </button>
              <p className="text-xs text-muted-foreground mt-1">單檔上限 25 MB，所有附件合計請勿超過 25 MB（Gmail 限制）</p>
              {emailAttachments.length > 0 && (
                <div className="mt-2 space-y-1">
                  {emailAttachments.map((file, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm bg-muted/50 rounded px-2 py-1">
                      <Paperclip className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                      <span className="flex-1 truncate">{file.name}</span>
                      <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</span>
                      <button
                        type="button"
                        onClick={() => setEmailAttachments(prev => prev.filter((_, idx) => idx !== i))}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Schedule option */}
            <div className="border rounded-lg p-3 bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  id="schedule-mode"
                  checked={scheduleMode}
                  onChange={e => setScheduleMode(e.target.checked)}
                  className="rounded"
                />
                <Label htmlFor="schedule-mode" className="cursor-pointer flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" /> 排程發送
                </Label>
              </div>
              {scheduleMode && (
                <div>
                  <Label className="text-xs">發送時間</Label>
                  <Input
                    type="datetime-local"
                    value={scheduledAt}
                    onChange={e => setScheduledAt(e.target.value)}
                    className="mt-1 text-sm"
                  />
                  {scheduledAt && (
                    <p className="text-xs text-muted-foreground mt-1">
                      預計於 {format(new Date(scheduledAt), 'yyyy/MM/dd HH:mm')} 送出
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowEmail(false)}>取消</Button>
              <Button onClick={handleSendEmail} disabled={sendingEmail}>
                {sendingEmail ? '處理中...' : scheduleMode ? '排程發送' : '立即發送'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* AI Email Modal */}
      {showAiEmailModal && (
        <AiEmailModal
          lead={lead}
          onClose={() => setShowAiEmailModal(false)}
          onApply={(subject, body) => {
            setEmailSubject(subject)
            setEmailBody(body)
            setShowAiEmailModal(false)
            setShowEmail(true)
          }}
        />
      )}

      {/* Proposal Modal */}
      <Dialog open={showProposalModal} onOpenChange={v => { setShowProposalModal(v); if (!v) setProposalResult(null) }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>📋 生成提案信</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>主推產品</Label>
                <Select value={proposalProduct} onValueChange={setProposalProduct}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {['廣告投放', 'SEO優化', '社群代操', '整合行銷', 'KOL行銷', '程序化廣告'].map(p => (
                      <SelectItem key={p} value={p}>{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>語氣</Label>
                <Select value={proposalTone} onValueChange={setProposalTone}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">專業正式</SelectItem>
                    <SelectItem value="friendly">親切友善</SelectItem>
                    <SelectItem value="urgent">急迫有力</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button onClick={handleGenerateProposal} disabled={generatingProposal} className="w-full">
              <Sparkles className="w-4 h-4 mr-2" />
              {generatingProposal ? '生成中...' : '生成提案信'}
            </Button>

            {proposalResult && (
              <div className="space-y-3">
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-xs font-medium text-muted-foreground mb-1">信件主旨</p>
                  <p className="text-sm font-medium">{proposalResult.subject}</p>
                </div>
                {proposalResult.key_points.length > 0 && (
                  <div className="p-3 bg-blue-50 rounded-lg">
                    <p className="text-xs font-medium text-blue-600 mb-1">重點摘要</p>
                    <ul className="space-y-1">
                      {proposalResult.key_points.map((pt, i) => (
                        <li key={i} className="text-xs text-blue-700">• {pt}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">信件正文</p>
                  <Textarea
                    value={proposalResult.body}
                    onChange={e => setProposalResult(r => r ? { ...r, body: e.target.value } : r)}
                    rows={12}
                    className="text-sm"
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" size="sm" onClick={() => {
                    if (!proposalResult) return
                    navigator.clipboard.writeText(`主旨：${proposalResult.subject}\n\n${proposalResult.body}`)
                    alert('✅ 已複製到剪貼簿')
                  }}>
                    複製
                  </Button>
                  <Button size="sm" onClick={() => {
                    if (!proposalResult) return
                    setEmailSubject(proposalResult.subject)
                    setEmailBody(proposalResult.body)
                    setShowProposalModal(false)
                    setShowEmail(true)
                  }}>
                    套用到發信
                  </Button>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── AI Email Modal ─────────────────────────────────────────────────────────────

function AiEmailModal({ lead, onClose, onApply }: {
  lead: { id: string; website?: string | null; company_name: string }
  onClose: () => void
  onApply: (subject: string, body: string) => void
}) {
  const [websiteUrl, setWebsiteUrl] = useState(lead.website || '')
  const [product, setProduct] = useState('SEO優化')
  const [tone, setTone] = useState('professional')
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<{ subject: string; body: string } | null>(null)

  const PRODUCTS = ['SEO優化', '廣告投放', '社群代操', '整合行銷', 'KOL行銷']
  const TONES = [
    { value: 'professional', label: '專業' },
    { value: 'friendly', label: '親切' },
    { value: 'urgent', label: '急迫' },
  ]

  const handleGenerate = async () => {
    if (!websiteUrl) { alert('請輸入官網 URL'); return }
    setGenerating(true)
    try {
      const res = await generateEmail({ website_url: websiteUrl, product, lead_id: lead.id, tone })
      setResult({ subject: res.data.subject, body: res.data.body })
    } catch (e: unknown) {
      alert((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'AI 生成失敗')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>✨ AI 客製化 Email</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>客戶官網</Label>
            <Input value={websiteUrl} onChange={e => setWebsiteUrl(e.target.value)} placeholder="https://..." className="mt-1" />
          </div>
          <div>
            <Label>主推產品</Label>
            <Select value={product} onValueChange={setProduct}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                {PRODUCTS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>語氣</Label>
            <Select value={tone} onValueChange={setTone}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TONES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleGenerate} disabled={generating} className="w-full">
            <Sparkles className="w-4 h-4 mr-2" />
            {generating ? '生成中...' : '生成 Email'}
          </Button>
          {result && (
            <div className="border rounded-lg p-4 bg-gray-50 space-y-2">
              <div>
                <p className="text-xs text-muted-foreground mb-1">主旨</p>
                <p className="text-sm font-medium">{result.subject}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">內文</p>
                <p className="text-sm whitespace-pre-wrap">{result.body}</p>
              </div>
              <Button size="sm" onClick={() => onApply(result.subject, result.body)} className="w-full">
                套用至發信欄位
              </Button>
            </div>
          )}
          <div className="flex justify-end">
            <Button variant="outline" onClick={onClose}>關閉</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
