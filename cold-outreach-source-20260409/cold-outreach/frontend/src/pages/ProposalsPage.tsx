import { useState, useEffect, useCallback } from 'react'
import {
  getProposals, generateProposal, deleteProposal, updateProposal, getLeads, exportProposalPptx,
  listProposalTemplates, uploadProposalTemplate, activateProposalTemplate, deleteProposalTemplate,
  generateProposalFromLead,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Plus, Trash2, Mail, ChevronDown, ChevronUp, Copy, CheckCheck,
  Loader2, FileText, BarChart3, Lightbulb, DollarSign, Building2, Download,
  Upload, CheckCircle2, X, FolderOpen, Paperclip,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface FunnelStage {
  stage: string
  objective: string
  channels: string[]
  audience: string
  kpi: string
}

interface ProposalContent {
  phase1?: {
    title: string
    headline: string
    stats: { label: string; value: string }[]
    certifications: string[]
    services: string[]
    client_industries: string[]
  }
  phase2?: {
    title: string
    current_diagnosis: string
    recommended_approach: string
    funnel: FunnelStage[]
    key_insight: string
  }
  phase3?: {
    title: string
    benchmarks: {
      industry_avg_roas: string
      industry_avg_cpc: string
      industry_avg_ctr: string
      industry_avg_cvr: string
    }
    competitive_gap: string
    growth_opportunities: string[]
  }
  phase4?: {
    title: string
    recommended_formats: string[]
    creative_dimensions: {
      trust_building: { name: string; description: string; examples: string[] }
      pain_point: { name: string; description: string; examples: string[] }
      conversion: { name: string; description: string; examples: string[] }
    }
  }
  phase5?: {
    title: string
    monthly_budget: string
    channel_allocation: { channel: string; percentage: number; rationale: string }[]
    key_campaigns: { name: string; timing: string; focus: string }[]
    expected_roas: string
    timeline_note: string
  }
}

interface Proposal {
  id: string
  lead_id: string
  company_name: string
  lead_industry: string
  title: string
  product_focus: string
  budget_range: string
  status: 'draft' | 'sent'
  content: ProposalContent | null
  email_subject: string
  email_body: string
  created_at: string
}

interface Lead {
  id: string
  company_name: string
  industry: string
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PRODUCT_OPTIONS = [
  '廣告投放', 'SEO優化', '社群代操', '整合行銷', 'KOL行銷', '程序化廣告',
]

const BUDGET_OPTIONS = [
  '10-30萬/月', '30-50萬/月', '50-100萬/月', '100萬以上/月',
]

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-700',
  sent: 'bg-green-100 text-green-700',
}
const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  sent: '已寄出',
}

const PHASE_ICONS = [Building2, BarChart3, BarChart3, Lightbulb, DollarSign]
const PHASE_COLORS = [
  'bg-blue-50 border-blue-200',
  'bg-indigo-50 border-indigo-200',
  'bg-teal-50 border-teal-200',
  'bg-purple-50 border-purple-200',
  'bg-orange-50 border-orange-200',
]

// ── Template Manager ──────────────────────────────────────────────────────────

interface PptTemplate {
  filename: string
  size_kb: number
  active: boolean
}

function TemplateManager() {
  const [open, setOpen] = useState(false)
  const [templates, setTemplates] = useState<PptTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await listProposalTemplates()
      setTemplates(Array.isArray(res.data) ? res.data : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) load()
  }, [open])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await uploadProposalTemplate(file)
      await load()
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '未知錯誤'
      alert(`上傳失敗：${detail}`)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleActivate = async (filename: string) => {
    await activateProposalTemplate(filename)
    await load()
  }

  const handleDelete = async (filename: string) => {
    if (!confirm(`確定刪除 ${filename}？`)) return
    await deleteProposalTemplate(filename)
    await load()
  }

  return (
    <div className="mb-5 border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 text-sm font-medium text-slate-700 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <span className="flex items-center gap-2">
          <FolderOpen className="w-4 h-4 text-slate-500" />
          PPT 範本庫
          <span className="text-xs text-slate-400 font-normal">上傳更多 PPTX 讓 AI 學習您的設計風格</span>
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>

      {open && (
        <div className="p-4 bg-white">
          {/* Upload button */}
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="file"
              accept=".pptx"
              className="hidden"
              onChange={handleFileChange}
              disabled={uploading}
            />
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors">
              {uploading
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Upload className="w-3.5 h-3.5" />}
              {uploading ? '上傳中...' : '上傳 PPTX'}
            </span>
          </label>
          <p className="text-xs text-slate-400 mt-1 mb-3">
            支援 .pptx 格式 · 上傳後可設為設計參考 · 系統將擷取配色與字型，下次產生 PPT 即套用
          </p>

          {/* Template list */}
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-400 py-2">
              <Loader2 className="w-4 h-4 animate-spin" /> 載入中...
            </div>
          ) : templates.length === 0 ? (
            <p className="text-sm text-slate-400 py-2">尚無範本（使用內建 Wavenet 範本）</p>
          ) : (
            <div className="space-y-2">
              {templates.map(tpl => (
                <div
                  key={tpl.filename}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg border text-sm ${
                    tpl.active
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-200 bg-white'
                  }`}
                >
                  <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                  <span className="flex-1 font-medium text-slate-700 truncate">{tpl.filename}</span>
                  <span className="text-xs text-slate-400">{tpl.size_kb} KB</span>

                  {tpl.active ? (
                    <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-medium shrink-0">
                      <CheckCircle2 className="w-3.5 h-3.5" /> 設計參考中
                    </span>
                  ) : (
                    <button
                      onClick={() => handleActivate(tpl.filename)}
                      className="text-xs text-blue-600 hover:underline shrink-0"
                    >
                      設為設計參考
                    </button>
                  )}

                  {tpl.filename !== 'wavenet_template.pptx' && (
                    <button
                      onClick={() => handleDelete(tpl.filename)}
                      className="text-slate-400 hover:text-red-500 shrink-0"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Generate Dialog (merged) ───────────────────────────────────────────────────

function GenerateDialog({
  onClose,
  onGenerated,
}: {
  onClose: () => void
  onGenerated: () => void
}) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [form, setForm] = useState({
    lead_id: '',
    services: ['廣告投放', 'SEO優化'],
    budget_range: '50-100萬/月',
    client_type: 'b2c',
    extra_context: '',
    year: new Date().getFullYear() + 1,
  })
  const [contextFiles, setContextFiles] = useState<Array<{ file: File; preview?: string }>>([])
  const [search, setSearch] = useState('')
  const [generating, setGenerating] = useState(false)
  const [downloadingPptx, setDownloadingPptx] = useState(false)

  useEffect(() => {
    getLeads({ limit: 200 }).then(r => {
      const data = r.data
      setLeads(Array.isArray(data) ? data : data?.items || [])
    })
  }, [])

  const filtered = leads.filter(l =>
    l.company_name.toLowerCase().includes(search.toLowerCase())
  )

  const busy = generating || downloadingPptx

  const handleContextFileAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    Array.from(e.target.files || []).forEach(file => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader()
        reader.onload = ev => setContextFiles(prev => [...prev, { file, preview: ev.target?.result as string }])
        reader.readAsDataURL(file)
      } else {
        setContextFiles(prev => [...prev, { file }])
      }
    })
    e.target.value = ''
  }

  const handleDownloadPptx = async () => {
    if (!form.lead_id) return
    setDownloadingPptx(true)
    try {
      let extraContext = form.extra_context
      for (const cf of contextFiles.filter(cf => !cf.preview)) {
        const text = await cf.file.text()
        extraContext += `\n\n【參考文件：${cf.file.name}】\n${text}`
      }

      const res = await generateProposalFromLead({
        lead_id: form.lead_id,
        services: form.services,
        budget_range: form.budget_range,
        client_type: form.client_type,
        extra_context: extraContext,
        year: form.year,
      })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      const selectedLead = leads.find(l => l.id === form.lead_id)
      a.download = `${selectedLead?.company_name || '提案'}_${form.year}_媒體提案.pptx`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err: unknown) {
      const text = await (err as { response?: { data?: Blob } })?.response?.data?.text?.()
      try {
        const json = JSON.parse(text || '{}')
        alert(`下載失敗：${json.detail || String(err)}`)
      } catch {
        alert(`下載失敗，請稍後再試`)
      }
    } finally {
      setDownloadingPptx(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>產生提案</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {/* 客戶選擇 */}
          <div>
            <Label>選擇客戶 *</Label>
            <Input
              className="mt-1 mb-1"
              placeholder="搜尋公司名稱..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            <Select value={form.lead_id} onValueChange={v => setForm(f => ({ ...f, lead_id: v }))}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="請選擇客戶" />
              </SelectTrigger>
              <SelectContent className="max-h-52">
                {filtered.slice(0, 50).map(l => (
                  <SelectItem key={l.id} value={l.id}>
                    {l.company_name}{l.industry ? ` · ${l.industry}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 客戶類型 */}
          <div>
            <Label>客戶類型</Label>
            <div className="grid grid-cols-2 gap-2 mt-1">
              {[
                { value: 'b2c', label: 'B2C 消費者品牌' },
                { value: 'b2b_biotech', label: 'B2B 生技製藥' },
              ].map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setForm(f => ({ ...f, client_type: opt.value }))}
                  className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    form.client_type === opt.value
                      ? 'bg-primary/10 border-primary text-primary'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 服務（多選）+ 預算 */}
          <div className="space-y-3">
            <div>
              <Label>主推服務（可多選）</Label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {PRODUCT_OPTIONS.map(o => (
                  <button
                    key={o}
                    type="button"
                    onClick={() => setForm(f => ({
                      ...f,
                      services: f.services.includes(o)
                        ? f.services.filter(s => s !== o)
                        : [...f.services, o],
                    }))}
                    className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                      form.services.includes(o)
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                    }`}
                  >
                    {o}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label>預算規模</Label>
              <Select value={form.budget_range} onValueChange={v => setForm(f => ({ ...f, budget_range: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {BUDGET_OPTIONS.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 補充背景 */}
          <div>
            <Label>補充背景（選填）</Label>
            <Textarea
              className="mt-1 text-sm"
              rows={2}
              placeholder="例：主力商品為高單價3C，目前主要靠口碑，想開始投放廣告..."
              value={form.extra_context}
              onChange={e => setForm(f => ({ ...f, extra_context: e.target.value }))}
            />
            <div className="mt-2 flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7 px-2"
                type="button"
                onClick={() => document.getElementById('ctx-file-input')?.click()}
              >
                <Paperclip className="w-3 h-3 mr-1" />
                附加圖片 / 文字檔
              </Button>
              <span className="text-xs text-muted-foreground">PNG、JPG、TXT（AI 會一起參考）</span>
            </div>
            <input
              id="ctx-file-input"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,.txt"
              multiple
              className="hidden"
              onChange={handleContextFileAdd}
            />
            {contextFiles.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {contextFiles.map((cf, i) => (
                  <div key={i} className="relative group">
                    {cf.preview ? (
                      <div className="relative w-16 h-16">
                        <img src={cf.preview} alt={cf.file.name} className="w-16 h-16 object-cover rounded border" />
                        <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[8px] px-1 truncate rounded-b leading-4">
                          {cf.file.name}
                        </div>
                      </div>
                    ) : (
                      <div className="w-16 h-16 flex flex-col items-center justify-center border rounded bg-slate-50 gap-1 p-1">
                        <FileText className="w-4 h-4 text-muted-foreground" />
                        <span className="text-[9px] text-muted-foreground text-center leading-3 break-all line-clamp-2">{cf.file.name}</span>
                      </div>
                    )}
                    <button
                      type="button"
                      className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-destructive text-white rounded-full items-center justify-center hidden group-hover:flex"
                      onClick={() => setContextFiles(prev => prev.filter((_, j) => j !== i))}
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 操作按鈕 */}
          <div className="flex justify-end gap-2 border-t pt-3">
            <Button variant="outline" onClick={onClose} disabled={busy}>取消</Button>
            <Button onClick={handleDownloadPptx} disabled={!form.lead_id || form.services.length === 0 || busy}>
              {downloadingPptx
                ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" />AI 生成中，約需 30 秒...</>
                : <><Download className="w-4 h-4 mr-1.5" />下載 PPTX（16頁）</>}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Phase Sections ────────────────────────────────────────────────────────────

function Phase1({ data }: { data: ProposalContent['phase1'] }) {
  if (!data) return null
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-blue-700">{data.headline}</p>
      <div className="grid grid-cols-2 gap-2">
        {data.stats.map(s => (
          <div key={s.label} className="bg-white rounded p-2 border text-center">
            <p className="text-xs text-muted-foreground">{s.label}</p>
            <p className="font-bold text-sm mt-0.5">{s.value}</p>
          </div>
        ))}
      </div>
      <div>
        <p className="text-xs font-medium text-gray-500 mb-1">合作夥伴認證</p>
        <div className="flex flex-wrap gap-1.5">
          {data.certifications.map(c => (
            <span key={c} className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{c}</span>
          ))}
        </div>
      </div>
      <div>
        <p className="text-xs font-medium text-gray-500 mb-1">七大服務</p>
        <ul className="list-disc list-inside space-y-0.5">
          {data.services.map(s => <li key={s} className="text-xs text-gray-700">{s}</li>)}
        </ul>
      </div>
    </div>
  )
}

function Phase2({ data }: { data: ProposalContent['phase2'] }) {
  if (!data) return null
  const STAGE_COLORS = ['bg-sky-100', 'bg-indigo-100', 'bg-emerald-100', 'bg-rose-100']
  return (
    <div className="space-y-3">
      <div className="bg-amber-50 border border-amber-200 rounded p-3">
        <p className="text-xs font-medium text-amber-700 mb-1">現況診斷</p>
        <p className="text-sm text-gray-700">{data.current_diagnosis}</p>
      </div>
      <div className="bg-indigo-50 border border-indigo-200 rounded p-3">
        <p className="text-xs font-medium text-indigo-700 mb-1">策略建議</p>
        <p className="text-sm text-gray-700">{data.recommended_approach}</p>
      </div>
      <div>
        <p className="text-xs font-medium text-gray-500 mb-2">全漏斗規劃</p>
        <div className="space-y-2">
          {data.funnel.map((f, i) => (
            <div key={f.stage} className={`rounded p-3 ${STAGE_COLORS[i % 4]}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">{f.stage}</span>
                <span className="text-xs text-gray-500">{f.kpi}</span>
              </div>
              <p className="text-xs text-gray-600 mb-1">{f.objective}</p>
              <div className="flex flex-wrap gap-1">
                {f.channels.map(c => (
                  <span key={c} className="text-xs bg-white/70 px-1.5 py-0.5 rounded border">{c}</span>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-1">受眾：{f.audience}</p>
            </div>
          ))}
        </div>
      </div>
      {data.key_insight && (
        <div className="bg-gray-50 border rounded p-3">
          <p className="text-xs font-medium text-gray-500 mb-1">關鍵洞察</p>
          <p className="text-sm text-gray-700">💡 {data.key_insight}</p>
        </div>
      )}
    </div>
  )
}

function Phase3({ data }: { data: ProposalContent['phase3'] }) {
  if (!data) return null
  const bm = data.benchmarks || {}
  const bmItems = [
    { label: '產業平均 ROAS', value: bm.industry_avg_roas },
    { label: '產業平均 CPC', value: bm.industry_avg_cpc },
    { label: '產業平均 CTR', value: bm.industry_avg_ctr },
    { label: '產業平均 CVR', value: bm.industry_avg_cvr },
  ]
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {bmItems.map(b => b.value ? (
          <div key={b.label} className="bg-white border rounded p-2 text-center">
            <p className="text-xs text-muted-foreground">{b.label}</p>
            <p className="font-bold text-sm text-teal-700 mt-0.5">{b.value}</p>
          </div>
        ) : null)}
      </div>
      {data.competitive_gap && (
        <div className="bg-rose-50 border border-rose-200 rounded p-3">
          <p className="text-xs font-medium text-rose-700 mb-1">競爭差距分析</p>
          <p className="text-sm text-gray-700">{data.competitive_gap}</p>
        </div>
      )}
      {data.growth_opportunities?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">成長機會</p>
          <ul className="space-y-1">
            {data.growth_opportunities.map((o, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-700">
                <span className="text-teal-500 font-bold">✓</span> {o}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Phase4({ data }: { data: ProposalContent['phase4'] }) {
  if (!data) return null
  const dims = data.creative_dimensions || {} as NonNullable<ProposalContent['phase4']>['creative_dimensions']
  const dimList = [
    { key: 'trust_building', color: 'bg-blue-50 border-blue-200', badge: 'text-blue-700 bg-blue-100' },
    { key: 'pain_point', color: 'bg-orange-50 border-orange-200', badge: 'text-orange-700 bg-orange-100' },
    { key: 'conversion', color: 'bg-green-50 border-green-200', badge: 'text-green-700 bg-green-100' },
  ] as const
  return (
    <div className="space-y-3">
      {data.recommended_formats?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">建議廣告格式</p>
          <div className="flex flex-wrap gap-1.5">
            {data.recommended_formats.map(f => (
              <span key={f} className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">{f}</span>
            ))}
          </div>
        </div>
      )}
      <div className="space-y-2">
        {dimList.map(({ key, color, badge }) => {
          const dim = dims[key]
          if (!dim) return null
          return (
            <div key={key} className={`border rounded p-3 ${color}`}>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge}`}>{dim.name}</span>
              <p className="text-sm text-gray-700 mt-2">{dim.description}</p>
              {dim.examples?.length > 0 && (
                <ul className="mt-1.5 space-y-0.5">
                  {dim.examples.map((ex, i) => (
                    <li key={i} className="text-xs text-gray-500">→ {ex}</li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Phase5({ data }: { data: ProposalContent['phase5'] }) {
  if (!data) return null
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <div className="bg-orange-50 border border-orange-200 rounded p-3 flex-1 text-center">
          <p className="text-xs text-muted-foreground">月預算規模</p>
          <p className="font-bold text-orange-700">{data.monthly_budget}</p>
        </div>
        <div className="bg-green-50 border border-green-200 rounded p-3 flex-1 text-center">
          <p className="text-xs text-muted-foreground">預期 ROAS</p>
          <p className="font-bold text-green-700">{data.expected_roas}</p>
        </div>
      </div>

      {data.channel_allocation?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">媒體管道配置</p>
          <div className="space-y-1.5">
            {data.channel_allocation.map(c => (
              <div key={c.channel} className="flex items-center gap-2">
                <span className="text-xs text-gray-700 w-28 shrink-0">{c.channel}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-indigo-500 h-2 rounded-full"
                    style={{ width: `${Math.min(c.percentage, 100)}%` }}
                  />
                </div>
                <span className="text-xs font-bold w-8 text-right">{c.percentage}%</span>
              </div>
            ))}
          </div>
          <div className="mt-2 space-y-1">
            {data.channel_allocation.map(c => (
              <p key={c.channel} className="text-xs text-gray-500">
                <span className="font-medium text-gray-700">{c.channel}：</span>{c.rationale}
              </p>
            ))}
          </div>
        </div>
      )}

      {data.key_campaigns?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">關鍵節點活動</p>
          <div className="space-y-1.5">
            {data.key_campaigns.map((k, i) => (
              <div key={i} className="bg-white border rounded p-2 flex gap-2 text-xs">
                <span className="font-medium text-gray-800 shrink-0">{k.name}</span>
                <span className="text-gray-400">·</span>
                <span className="text-gray-500">{k.timing}</span>
                <span className="text-gray-400">·</span>
                <span className="text-gray-600">{k.focus}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.timeline_note && (
        <p className="text-xs text-gray-500 bg-gray-50 border rounded p-2">{data.timeline_note}</p>
      )}
    </div>
  )
}

// ── Proposal Detail Modal ─────────────────────────────────────────────────────

function ProposalDetailModal({
  proposal,
  onClose,
  onDeleted,
  onStatusChange,
}: {
  proposal: Proposal
  onClose: () => void
  onDeleted: () => void
  onStatusChange: (status: string) => void
}) {
  const [openPhases, setOpenPhases] = useState<Set<number>>(new Set([0]))
  const [copied, setCopied] = useState<'subject' | 'body' | null>(null)
  const [downloading, setDownloading] = useState(false)

  const handleDownloadPptx = async () => {
    setDownloading(true)
    try {
      const res = await exportProposalPptx(proposal.id)
      const url = URL.createObjectURL(new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
      }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${proposal.title || 'proposal'}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '未知錯誤'
      alert(`PPT 下載失敗：${detail}`)
    } finally {
      setDownloading(false)
    }
  }

  const togglePhase = (i: number) => {
    setOpenPhases(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const copyText = async (text: string, field: 'subject' | 'body') => {
    await navigator.clipboard.writeText(text)
    setCopied(field)
    setTimeout(() => setCopied(null), 2000)
  }

  const content = proposal.content
  const phases = [
    { label: content?.phase1?.title || '關於潮網科技', render: () => <Phase1 data={content?.phase1} /> },
    { label: content?.phase2?.title || '全漏斗策略規劃', render: () => <Phase2 data={content?.phase2} /> },
    { label: content?.phase3?.title || '市場數據洞察', render: () => <Phase3 data={content?.phase3} /> },
    { label: content?.phase4?.title || '廣告創意策略', render: () => <Phase4 data={content?.phase4} /> },
    { label: content?.phase5?.title || '媒體預算規劃', render: () => <Phase5 data={content?.phase5} /> },
  ]

  const handleDelete = async () => {
    if (!confirm('確定刪除此提案？')) return
    await deleteProposal(proposal.id)
    onDeleted()
    onClose()
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="pr-8">{proposal.title}</DialogTitle>
        </DialogHeader>

        {/* Meta bar */}
        <div className="flex flex-wrap gap-2 text-xs">
          <span className={`px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[proposal.status]}`}>
            {STATUS_LABELS[proposal.status]}
          </span>
          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{proposal.company_name}</span>
          {proposal.product_focus && (
            <span className="bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full">{proposal.product_focus}</span>
          )}
          {proposal.budget_range && (
            <span className="bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">{proposal.budget_range}</span>
          )}
          <div className="ml-auto flex gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="h-6 text-xs gap-1"
              onClick={handleDownloadPptx}
              disabled={downloading}
            >
              {downloading
                ? <Loader2 className="w-3 h-3 animate-spin" />
                : <Download className="w-3 h-3" />}
              下載 PPT
            </Button>
            {proposal.status === 'draft' && (
              <Button
                size="sm"
                variant="outline"
                className="h-6 text-xs"
                onClick={() => onStatusChange('sent')}
              >
                標記已寄出
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              className="h-6 text-xs text-destructive hover:text-destructive"
              onClick={handleDelete}
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* 5-phase accordion */}
        <div className="space-y-2">
          {phases.map((phase, i) => {
            const Icon = PHASE_ICONS[i]
            const isOpen = openPhases.has(i)
            return (
              <div key={i} className={`border rounded-lg overflow-hidden ${PHASE_COLORS[i]}`}>
                <button
                  className="w-full flex items-center justify-between px-4 py-3 text-left"
                  onClick={() => togglePhase(i)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-400">Phase {i + 1}</span>
                    <Icon className="w-3.5 h-3.5 text-gray-500" />
                    <span className="text-sm font-semibold text-gray-800">{phase.label}</span>
                  </div>
                  {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 border-t bg-white/60">
                    <div className="pt-3">
                      {phase.render()}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Companion email */}
        {(proposal.email_subject || proposal.email_body) && (
          <div className="border rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b">
              <Mail className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-semibold text-gray-800">配套開發信</span>
            </div>
            <div className="p-4 space-y-3">
              {proposal.email_subject && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-muted-foreground">主旨</p>
                    <button
                      className="text-xs text-blue-600 flex items-center gap-1 hover:underline"
                      onClick={() => copyText(proposal.email_subject, 'subject')}
                    >
                      {copied === 'subject' ? <CheckCheck className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      複製
                    </button>
                  </div>
                  <p className="text-sm font-medium bg-gray-50 rounded p-2">{proposal.email_subject}</p>
                </div>
              )}
              {proposal.email_body && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-muted-foreground">信件內文</p>
                    <button
                      className="text-xs text-blue-600 flex items-center gap-1 hover:underline"
                      onClick={() => copyText(proposal.email_body, 'body')}
                    >
                      {copied === 'body' ? <CheckCheck className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      複製
                    </button>
                  </div>
                  <pre className="text-sm whitespace-pre-wrap font-sans bg-gray-50 rounded p-3 max-h-64 overflow-y-auto">
                    {proposal.email_body}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [loading, setLoading] = useState(true)
  const [showGenerate, setShowGenerate] = useState(false)
  const [viewing, setViewing] = useState<Proposal | null>(null)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getProposals()
      setProposals(Array.isArray(res.data) ? res.data : [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleStatusChange = async (status: string) => {
    if (!viewing) return
    await updateProposal(viewing.id, { status })
    await load()
    setViewing(prev => prev ? { ...prev, status: status as Proposal['status'] } : null)
  }

  const filtered = proposals.filter(p =>
    p.company_name.toLowerCase().includes(search.toLowerCase()) ||
    p.title.toLowerCase().includes(search.toLowerCase()) ||
    (p.product_focus || '').includes(search)
  )

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">提案管理</h1>
          <p className="text-sm text-muted-foreground mt-0.5">AI 自動產生 5 階段數位行銷提案簡報</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowGenerate(true)}>
            <Plus className="w-4 h-4 mr-1.5" /> 產生提案
          </Button>
        </div>
      </div>

      <TemplateManager />

      <div className="mb-4">
        <Input
          placeholder="搜尋公司名稱、提案標題或服務類型..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8">
          <Loader2 className="w-4 h-4 animate-spin" /> 載入中...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {proposals.length === 0
              ? '尚無提案，點擊「產生提案」讓 AI 為您自動產生'
              : '沒有符合搜尋條件的提案'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(p => (
            <div
              key={p.id}
              className="bg-white border rounded-xl p-5 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setViewing(p)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                  <span className="font-medium text-sm truncate">{p.company_name}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ml-2 ${STATUS_COLORS[p.status]}`}>
                  {STATUS_LABELS[p.status]}
                </span>
              </div>
              <p className="text-xs text-gray-700 mb-2 line-clamp-2">{p.title}</p>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {p.product_focus && (
                  <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">{p.product_focus}</span>
                )}
                {p.budget_range && (
                  <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{p.budget_range}</span>
                )}
                {p.lead_industry && (
                  <span className="text-xs bg-indigo-100 text-indigo-600 px-1.5 py-0.5 rounded">{p.lead_industry}</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {new Date(p.created_at).toLocaleDateString('zh-TW')}
              </p>
            </div>
          ))}
        </div>
      )}

      {showGenerate && (
        <GenerateDialog
          onClose={() => setShowGenerate(false)}
          onGenerated={load}
        />
      )}

      {viewing && (
        <ProposalDetailModal
          proposal={viewing}
          onClose={() => setViewing(null)}
          onDeleted={load}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  )
}
