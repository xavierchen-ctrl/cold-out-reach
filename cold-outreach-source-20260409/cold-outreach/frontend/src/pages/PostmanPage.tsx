import { useState, useEffect, useCallback, useMemo } from 'react'
import { getLeads, getTemplates, postmanSend, getSentTemplates } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Mail, Loader2, Send, CheckCheck, AlertTriangle, Search } from 'lucide-react'

const MAX_PER_SEND = 50

interface Lead {
  id: string
  company_name: string
  contact_name?: string
  email?: string
  industry?: string
}
interface Template {
  id: string
  name: string
  subject: string
  body: string
}
interface SentEntry { template_id: string | null; template_name: string | null }
type SentMap = Record<string, SentEntry[]>

// 與後端 _norm_company 一致的公司名正規化（用於比對已寄送公司）
const COMPANY_SUFFIXES = [
  '股份有限公司', '有限公司', '股份公司', '企業社', '工作室', '公司',
  'co.,ltd.', 'co., ltd.', 'co.ltd', 'co ltd', 'ltd.', 'ltd', 'inc.', 'inc',
  'corporation', 'corp.', 'corp', 'company', 'co.', 'group', '集團',
]
function normCompany(name: string): string {
  let n = (name || '').trim().toLowerCase()
  for (const s of COMPANY_SUFFIXES) n = n.split(s).join('')
  n = n.replace(/台灣|臺灣|分公司|总公司|總公司/g, '')
  n = n.replace(/[\s\-_、,.()（）&·.]/g, '')
  return n
}

interface SendResult {
  sent: number
  skipped: number
  failed: number
  skipped_list: { company_name: string; reason: string }[]
  errors: { lead_id: string; error: string }[]
}

export default function PostmanPage() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [sentMap, setSentMap] = useState<SentMap>({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [checked, setChecked] = useState<Set<string>>(new Set())

  const [templateId, setTemplateId] = useState<string>('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')

  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<SendResult | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [lr, tr, sr] = await Promise.all([getLeads({ limit: 500 }), getTemplates(), getSentTemplates()])
      const ld = lr.data
      setLeads(Array.isArray(ld) ? ld : ld?.items || [])
      setTemplates(Array.isArray(tr.data) ? tr.data : [])
      setSentMap(sr.data || {})
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const selectedTemplate = templates.find(t => t.id === templateId) || null

  const applyTemplate = (id: string) => {
    setTemplateId(id)
    const t = templates.find(x => x.id === id)
    if (t) { setSubject(t.subject); setBody(t.body) }
  }

  const sentNamesFor = (companyName: string): string[] => {
    const entries = sentMap[normCompany(companyName)] || []
    return entries.map(e => e.template_name || '自訂').filter(Boolean)
  }

  // 此公司是否已寄過目前選定的模板（用於警示）
  const alreadyGotSelected = (companyName: string): boolean => {
    if (!selectedTemplate) return false
    const entries = sentMap[normCompany(companyName)] || []
    return entries.some(e => e.template_id === selectedTemplate.id)
  }

  const filtered = useMemo(() => {
    const kw = search.toLowerCase()
    return leads.filter(l =>
      (l.company_name || '').toLowerCase().includes(kw) ||
      (l.contact_name || '').toLowerCase().includes(kw) ||
      (l.email || '').toLowerCase().includes(kw)
    )
  }, [leads, search])

  const toggle = (id: string) => {
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else {
        if (next.size >= MAX_PER_SEND) {
          alert(`單次最多寄送 ${MAX_PER_SEND} 封`)
          return prev
        }
        next.add(id)
      }
      return next
    })
  }

  const toggleAllVisible = () => {
    const withEmail = filtered.filter(l => l.email)
    const allSelected = withEmail.length > 0 && withEmail.every(l => checked.has(l.id))
    if (allSelected) {
      setChecked(new Set())
    } else {
      setChecked(new Set(withEmail.slice(0, MAX_PER_SEND).map(l => l.id)))
    }
  }

  // 一鍵自動填滿：挑有 Email、公司尚未發過此模板的前 50 家（同公司只選一個）
  const autoFill = () => {
    const picked = new Set<string>()
    const usedNorms = new Set<string>()
    for (const l of filtered) {
      if (picked.size >= MAX_PER_SEND) break
      if (!l.email) continue
      const norm = normCompany(l.company_name)
      if (usedNorms.has(norm)) continue                       // 同公司只選一個
      if (selectedTemplate && alreadyGotSelected(l.company_name)) continue  // 已發過此模板的跳過
      picked.add(l.id)
      usedNorms.add(norm)
    }
    setChecked(picked)
    if (picked.size === 0) alert('沒有可自動填入的名單（可能都已寄過此模板，或都沒有 Email）')
  }

  const handleSend = async () => {
    if (checked.size === 0) return
    if (!subject.trim() || !body.trim()) { alert('請先填寫主旨與內文（可從上方選擇模板）'); return }
    if (!confirm(`確定寄送給已勾選的 ${checked.size} 位收件人？\n（同一家公司已寄過此模板的會自動跳過）`)) return
    setSending(true)
    setResult(null)
    try {
      const res = await postmanSend({
        lead_ids: [...checked],
        subject,
        body,
        template_id: selectedTemplate?.id || null,
        template_name: selectedTemplate?.name || null,
      })
      setResult(res.data)
      setChecked(new Set())
      await load()   // 重新載入已寄送標記
    } catch (e: any) {
      alert(e?.response?.data?.detail || '寄送失敗，請稍後再試')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex items-center gap-3 mb-1">
        <Mail className="w-6 h-6 text-primary" />
        <h1 className="text-xl font-bold">小郵差</h1>
      </div>
      <p className="text-sm text-muted-foreground mb-5">
        勾選名單批次寄信（單次上限 {MAX_PER_SEND} 封）。同一家公司已寄過同一模板會自動擋下，不會重複寄送。
      </p>

      {/* 寄信內容 */}
      <div className="bg-white border rounded-xl p-5 space-y-4 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label>選擇模板</Label>
            <Select value={templateId} onValueChange={applyTemplate}>
              <SelectTrigger className="mt-1"><SelectValue placeholder="選擇信件模板" /></SelectTrigger>
              <SelectContent>
                {templates.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>主旨</Label>
            <Input className="mt-1" value={subject} onChange={e => setSubject(e.target.value)} placeholder="信件主旨（可用 {{company_name}} 變數）" />
          </div>
        </div>
        <div>
          <Label>內文</Label>
          <Textarea className="mt-1 text-sm" rows={6} value={body} onChange={e => setBody(e.target.value)}
            placeholder="信件內文，可用變數：{{company_name}} {{contact_name}} {{industry}} {{city}} {{title}}" />
          <p className="text-xs text-muted-foreground mt-1">可用變數：{'{{company_name}} {{contact_name}} {{industry}} {{city}} {{title}}'}（寄送時自動帶入各收件人資料）</p>
        </div>
      </div>

      {/* 寄送結果 */}
      {result && (
        <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 mb-4">
          <div className="flex items-center gap-2 text-sm font-medium text-green-800">
            <CheckCheck className="w-4 h-4" />
            寄送完成：成功 {result.sent} 封、自動跳過 {result.skipped} 封、失敗 {result.failed} 封
          </div>
          {result.skipped_list?.length > 0 && (
            <div className="mt-2 text-xs text-amber-700">
              <p className="flex items-center gap-1 font-medium"><AlertTriangle className="w-3.5 h-3.5" />跳過（已寄過此模板）：</p>
              <ul className="list-disc list-inside mt-0.5">
                {result.skipped_list.map((s, i) => <li key={i}>{s.company_name}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 工具列 */}
      <div className="flex items-center gap-3 mb-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="搜尋公司 / 聯絡人 / Email..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <Button variant="outline" onClick={autoFill} title="自動勾選有 Email、且公司尚未發過此模板的前 50 家">
          ⚡ 自動填滿 50
        </Button>
        <span className="text-sm text-muted-foreground">已選 <span className="font-bold text-indigo-700">{checked.size}</span> / {MAX_PER_SEND}</span>
        <Button onClick={handleSend} disabled={sending || checked.size === 0}>
          {sending ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" />寄送中...</> : <><Send className="w-4 h-4 mr-1.5" />寄送（{checked.size}）</>}
        </Button>
      </div>

      {/* 名單列表 */}
      <div className="bg-white border rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground p-8"><Loader2 className="w-4 h-4 animate-spin" /> 載入中...</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3 w-10 text-left">
                  <input type="checkbox" className="rounded"
                    checked={filtered.filter(l => l.email).length > 0 && filtered.filter(l => l.email).every(l => checked.has(l.id))}
                    onChange={toggleAllVisible} />
                </th>
                <th className="px-4 py-3 text-left font-medium">公司</th>
                <th className="px-4 py-3 text-left font-medium">聯絡人</th>
                <th className="px-4 py-3 text-left font-medium">Email</th>
                <th className="px-4 py-3 text-left font-medium">已發模板</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(l => {
                const noEmail = !l.email
                const sentNames = sentNamesFor(l.company_name)
                const dupWarn = alreadyGotSelected(l.company_name)
                return (
                  <tr key={l.id}
                    className={`border-t ${noEmail ? 'opacity-50' : 'hover:bg-muted/30 cursor-pointer'} ${checked.has(l.id) ? 'bg-indigo-50' : ''}`}
                    onClick={() => !noEmail && toggle(l.id)}>
                    <td className="px-4 py-2.5">
                      <input type="checkbox" className="rounded" disabled={noEmail}
                        checked={checked.has(l.id)} onChange={() => toggle(l.id)} onClick={e => e.stopPropagation()} />
                    </td>
                    <td className="px-4 py-2.5 font-medium">{l.company_name}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{l.contact_name || '—'}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{l.email || <span className="text-red-400">無 Email</span>}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {sentNames.length === 0 ? <span className="text-xs text-muted-foreground">—</span> :
                          sentNames.map((n, i) => (
                            <span key={i} className={`text-xs px-1.5 py-0.5 rounded ${dupWarn && selectedTemplate?.name === n ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>
                              ✉ {n}
                            </span>
                          ))}
                      </div>
                    </td>
                  </tr>
                )
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">沒有符合的名單</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
