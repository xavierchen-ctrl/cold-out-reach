import { useState, useEffect, useCallback } from 'react'
import { getSequences, createSequence, deleteSequence, getPendingEmails, sendPendingEmail, skipPendingEmail, processSequences, getTemplates } from '@/lib/api'
import { EmailTemplate } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Trash2, Mail, RefreshCw, Send, X } from 'lucide-react'

interface Step { day: number; template_type: string; subject?: string; body?: string }
interface Sequence { id: string; name: string; steps: Step[]; enrollment_count: number; created_at: string }
interface PendingEmail { id: string; lead_id: string; company_name: string; to_email: string; subject: string; body: string; status: string; created_at: string }

const TEMPLATE_LABELS: Record<string, string> = { intro: '初次開發', followup: '追蹤跟進', proposal: '報價提案' }

export default function SequencesPage() {
  const [sequences, setSequences] = useState<Sequence[]>([])
  const [pending, setPending] = useState<PendingEmail[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [activeTab, setActiveTab] = useState<'sequences' | 'pending'>('sequences')
  const [processing, setProcessing] = useState(false)
  const [previewEmail, setPreviewEmail] = useState<PendingEmail | null>(null)

  const load = useCallback(async () => {
    const [sq, pe] = await Promise.all([getSequences(), getPendingEmails()])
    setSequences(sq.data)
    setPending(pe.data)
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此序列？')) return
    await deleteSequence(id)
    load()
  }

  const handleProcess = async () => {
    setProcessing(true)
    try {
      const res = await processSequences()
      alert(`處理完成：${res.data.emails_created} 封待發信件已產生`)
      load()
    } finally {
      setProcessing(false)
    }
  }

  const handleSend = async (id: string) => {
    await sendPendingEmail(id)
    load()
  }

  const handleSkip = async (id: string) => {
    await skipPendingEmail(id)
    load()
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">發信序列</h1>
          <p className="text-sm text-muted-foreground mt-0.5">自動化多步驟跟進流程</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleProcess} disabled={processing}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${processing ? 'animate-spin' : ''}`} />
            處理到期序列
          </Button>
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4 mr-1.5" /> 建立序列
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b">
        {[{ key: 'sequences', label: `序列管理 (${sequences.length})` }, { key: 'pending', label: `待發信件 (${pending.length})` }].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as 'sequences' | 'pending')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === tab.key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sequences tab */}
      {activeTab === 'sequences' && (
        <div className="space-y-3">
          {sequences.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <p>尚無序列</p>
              <p className="text-sm mt-1">建立一個多步驟發信序列</p>
            </div>
          ) : sequences.map(seq => (
            <div key={seq.id} className="bg-white border rounded-xl p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">{seq.name}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">已加入 {seq.enrollment_count} 筆名單</p>
                </div>
                <button onClick={() => handleDelete(seq.id)} className="text-muted-foreground hover:text-destructive">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="flex gap-2 mt-3 flex-wrap">
                {seq.steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-1.5 bg-muted px-3 py-1.5 rounded-full text-xs">
                    <span className="font-medium text-primary">D{step.day}</span>
                    <span>{TEMPLATE_LABELS[step.template_type] || step.template_type}</span>
                    {i < seq.steps.length - 1 && <span className="text-muted-foreground ml-1">→</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pending emails tab */}
      {activeTab === 'pending' && (
        <div className="space-y-2">
          {pending.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <Mail className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p>暫無待發信件</p>
              <p className="text-sm mt-1">點擊「處理到期序列」產生待發信件</p>
            </div>
          ) : pending.map(email => (
            <div key={email.id} className="bg-white border rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm">{email.company_name}</span>
                    <span className="text-xs text-muted-foreground">{email.to_email}</span>
                  </div>
                  <p className="text-sm text-gray-700 truncate">{email.subject}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {new Date(email.created_at).toLocaleString('zh-TW')}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button variant="outline" size="sm" onClick={() => setPreviewEmail(email)}>預覽</Button>
                  <Button variant="outline" size="sm" onClick={() => handleSkip(email.id)}>
                    <X className="w-3.5 h-3.5" />
                  </Button>
                  <Button size="sm" onClick={() => handleSend(email.id)}>
                    <Send className="w-3.5 h-3.5 mr-1" /> 發送
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create sequence modal */}
      {showCreate && <CreateSequenceModal onClose={() => setShowCreate(false)} onCreated={load} />}

      {/* Preview modal */}
      {previewEmail && (
        <Dialog open onOpenChange={() => setPreviewEmail(null)}>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader><DialogTitle>信件預覽</DialogTitle></DialogHeader>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">收件人</p>
                <p>{previewEmail.to_email}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">主旨</p>
                <p className="font-medium">{previewEmail.subject}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">內文</p>
                <p className="whitespace-pre-wrap bg-muted p-3 rounded text-xs">{previewEmail.body}</p>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

function CreateSequenceModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [steps, setSteps] = useState<Step[]>([{ day: 1, template_type: 'intro' }])
  const [saving, setSaving] = useState(false)
  const [templates, setTemplates] = useState<EmailTemplate[]>([])

  useEffect(() => {
    getTemplates().then(r => setTemplates(Array.isArray(r.data) ? r.data : [])).catch(() => {})
  }, [])

  const addStep = () => {
    const lastDay = steps[steps.length - 1]?.day || 0
    setSteps(s => [...s, { day: lastDay + 3, template_type: 'followup' }])
  }
  const removeStep = (i: number) => setSteps(s => s.filter((_, idx) => idx !== i))
  const updateStep = (i: number, field: keyof Step, value: string | number) =>
    setSteps(s => s.map((st, idx) => idx === i ? { ...st, [field]: value } : st))

  const applyTemplate = (stepIdx: number, templateId: string) => {
    const tmpl = templates.find(t => t.id === templateId)
    if (!tmpl) return
    setSteps(s => s.map((st, idx) => idx === stepIdx ? {
      ...st,
      template_type: tmpl.template_type || st.template_type,
      subject: tmpl.subject,
      body: tmpl.body,
    } : st))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await createSequence({ name, steps })
      onCreated()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle>建立發信序列</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>序列名稱</Label>
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="例：數位行銷標準開發流程" required />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label>步驟設定</Label>
              <Button type="button" variant="ghost" size="sm" onClick={addStep}>
                <Plus className="w-3.5 h-3.5 mr-1" /> 新增步驟
              </Button>
            </div>
            <div className="space-y-3">
              {steps.map((step, i) => (
                <div key={i} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-5">{i + 1}.</span>
                    <div className="flex items-center gap-1">
                      <span className="text-xs">D</span>
                      <Input
                        type="number" min={1} value={step.day}
                        onChange={e => updateStep(i, 'day', parseInt(e.target.value))}
                        className="w-16 h-8 text-sm"
                      />
                    </div>
                    <Select value={step.template_type} onValueChange={v => updateStep(i, 'template_type', v)}>
                      <SelectTrigger className="flex-1 h-8"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="intro">初次開發</SelectItem>
                        <SelectItem value="followup">追蹤跟進</SelectItem>
                        <SelectItem value="proposal">報價提案</SelectItem>
                      </SelectContent>
                    </Select>
                    {steps.length > 1 && (
                      <button type="button" onClick={() => removeStep(i)} className="text-muted-foreground hover:text-destructive">
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                  {/* 套用模板 */}
                  {templates.length > 0 && (
                    <div>
                      <Label className="text-xs text-muted-foreground">套用模板（選填）</Label>
                      <Select onValueChange={v => applyTemplate(i, v)}>
                        <SelectTrigger className="h-7 text-xs mt-0.5"><SelectValue placeholder="選擇模板自動填入內容" /></SelectTrigger>
                        <SelectContent>
                          {templates.map(t => (
                            <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  {step.subject && (
                    <p className="text-xs text-muted-foreground bg-gray-50 px-2 py-1 rounded">
                      主旨：{step.subject}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>取消</Button>
            <Button type="submit" disabled={saving}>{saving ? '建立中...' : '建立序列'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
