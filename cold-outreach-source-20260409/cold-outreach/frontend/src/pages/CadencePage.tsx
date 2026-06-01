import { useState, useEffect, useCallback } from 'react'
import {
  getCadences, createCadence, deleteCadence, updateCadence,
  enrollCadence, getCadenceEnrollments, advanceEnrollment, skipStep,
  pauseEnrollment, resumeEnrollment, getLeads, getTemplates,
} from '@/lib/api'
import { Cadence, CadenceStep, CadenceEnrollment, CadenceStepType, Lead, EmailTemplate } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Trash2, Play, Pause, SkipForward, ChevronRight } from 'lucide-react'

const STEP_ICONS: Record<CadenceStepType, string> = {
  email: '📧',
  call: '📞',
  linkedin: '🔗',
  sms: '💬',
}

const STEP_TYPE_OPTIONS: { value: CadenceStepType; label: string }[] = [
  { value: 'email', label: '📧 Email' },
  { value: 'call', label: '📞 電話' },
  { value: 'linkedin', label: '🔗 LinkedIn' },
  { value: 'sms', label: '💬 SMS' },
]

function StepTimeline({ steps }: { steps: CadenceStep[] }) {
  return (
    <div className="space-y-0">
      {steps.map((step, i) => (
        <div key={i} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="w-8 h-8 rounded-full bg-primary/10 border-2 border-primary flex items-center justify-center text-sm font-bold text-primary">
              D{step.day}
            </div>
            {i < steps.length - 1 && <div className="w-0.5 h-8 bg-gray-200 my-1" />}
          </div>
          <div className="pb-4 flex-1">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-base">{STEP_ICONS[step.type]}</span>
              <span className="text-sm font-medium capitalize">{step.type}</span>
              {step.subject && (
                <span className="text-xs text-muted-foreground">— {step.subject}</span>
              )}
            </div>
            {step.note && <p className="text-xs text-gray-600">{step.note}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

function EnrollmentRow({
  enrollment,
  onAdvance,
  onSkip,
  onPause,
  onResume,
}: {
  enrollment: CadenceEnrollment
  onAdvance: () => void
  onSkip: () => void
  onPause: () => void
  onResume: () => void
}) {
  const progress = enrollment.total_steps > 0
    ? Math.round((enrollment.current_step / enrollment.total_steps) * 100)
    : 0

  const statusColor = {
    active: 'bg-green-100 text-green-700',
    paused: 'bg-yellow-100 text-yellow-700',
    completed: 'bg-blue-100 text-blue-700',
  }[enrollment.status] || 'bg-gray-100 text-gray-700'

  return (
    <div className="border rounded-lg p-3 bg-white">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm truncate">{enrollment.company_name}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusColor}`}>{enrollment.status}</span>
          </div>
          <p className="text-xs text-muted-foreground">{enrollment.contact_name}</p>
          <div className="mt-2">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {enrollment.current_step}/{enrollment.total_steps}
              </span>
            </div>
            {enrollment.current_step_info && (
              <p className="text-xs text-muted-foreground">
                目前：{STEP_ICONS[enrollment.current_step_info.type as CadenceStepType]}{' '}
                {enrollment.current_step_info.note || enrollment.current_step_info.type}
              </p>
            )}
            {enrollment.next_action_at && enrollment.status === 'active' && (
              <p className="text-xs text-orange-600 mt-0.5">
                下次：{new Date(enrollment.next_action_at).toLocaleDateString('zh-TW')}
              </p>
            )}
          </div>
        </div>
        {enrollment.status !== 'completed' && (
          <div className="flex flex-col gap-1 flex-shrink-0">
            <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={onAdvance}>
              <ChevronRight className="w-3 h-3 mr-1" /> 完成步驟
            </Button>
            <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={onSkip}>
              <SkipForward className="w-3 h-3 mr-1" /> 跳過
            </Button>
            {enrollment.status === 'active' ? (
              <Button size="sm" variant="outline" className="h-7 px-2 text-xs text-yellow-600" onClick={onPause}>
                <Pause className="w-3 h-3 mr-1" /> 暫停
              </Button>
            ) : (
              <Button size="sm" variant="outline" className="h-7 px-2 text-xs text-green-600" onClick={onResume}>
                <Play className="w-3 h-3 mr-1" /> 繼續
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function CadencePage() {
  const [cadences, setCadences] = useState<Cadence[]>([])
  const [selected, setSelected] = useState<Cadence | null>(null)
  const [enrollments, setEnrollments] = useState<CadenceEnrollment[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [showEnroll, setShowEnroll] = useState(false)
  const [leads, setLeads] = useState<Lead[]>([])
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [selectedLeads, setSelectedLeads] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  // Create form
  const [formName, setFormName] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formSteps, setFormSteps] = useState<CadenceStep[]>([
    { day: 1, type: 'email', note: '' }
  ])

  const loadCadences = useCallback(async () => {
    const res = await getCadences()
    setCadences(Array.isArray(res.data) ? res.data : [])
  }, [])

  const loadEnrollments = useCallback(async (cadenceId: string) => {
    const res = await getCadenceEnrollments(cadenceId)
    setEnrollments(Array.isArray(res.data) ? res.data : [])
  }, [])

  useEffect(() => {
    loadCadences()
    getTemplates().then(r => setTemplates(Array.isArray(r.data) ? r.data : [])).catch(() => {})
  }, [loadCadences])

  useEffect(() => {
    if (selected) {
      loadEnrollments(selected.id)
    }
  }, [selected, loadEnrollments])

  const handleSelectCadence = (c: Cadence) => {
    setSelected(c)
  }

  const handleCreate = async () => {
    if (!formName.trim()) return
    setLoading(true)
    try {
      await createCadence({ name: formName, description: formDesc, steps: formSteps })
      setShowCreate(false)
      setFormName('')
      setFormDesc('')
      setFormSteps([{ day: 1, type: 'email', note: '' }])
      await loadCadences()
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此 Cadence？')) return
    await deleteCadence(id)
    if (selected?.id === id) setSelected(null)
    await loadCadences()
  }

  const handleEnroll = async () => {
    if (!selected || selectedLeads.length === 0) return
    setLoading(true)
    try {
      const res = await enrollCadence(selected.id, selectedLeads)
      alert(`✅ 加入完成：${res.data.enrolled} 筆，已跳過 ${res.data.skipped} 筆`)
      setShowEnroll(false)
      setSelectedLeads([])
      await loadEnrollments(selected.id)
    } finally {
      setLoading(false)
    }
  }

  const openEnroll = async () => {
    const res = await getLeads()
    setLeads(Array.isArray(res.data) ? res.data : [])
    setShowEnroll(true)
  }

  const handleAdvance = async (enrollmentId: string) => {
    await advanceEnrollment(enrollmentId)
    if (selected) await loadEnrollments(selected.id)
  }

  const handleSkip = async (enrollmentId: string) => {
    await skipStep(enrollmentId)
    if (selected) await loadEnrollments(selected.id)
  }

  const handlePause = async (enrollmentId: string) => {
    await pauseEnrollment(enrollmentId)
    if (selected) await loadEnrollments(selected.id)
  }

  const handleResume = async (enrollmentId: string) => {
    await resumeEnrollment(enrollmentId)
    if (selected) await loadEnrollments(selected.id)
  }

  const addStep = () => {
    const lastDay = formSteps[formSteps.length - 1]?.day || 0
    setFormSteps(s => [...s, { day: lastDay + 3, type: 'email', note: '' }])
  }

  const removeStep = (i: number) => {
    setFormSteps(s => s.filter((_, idx) => idx !== i))
  }

  const updateStep = (i: number, updates: Partial<CadenceStep>) => {
    setFormSteps(s => s.map((step, idx) => idx === i ? { ...step, ...updates } : step))
  }

  return (
    <div className="flex h-full">
      {/* Left: Cadence list */}
      <aside className="w-72 border-r bg-white flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold">🎯 Cadence 波段</h2>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="w-3.5 h-3.5 mr-1" /> 建立
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {cadences.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">尚無 Cadence</p>
          ) : cadences.map(c => (
            <div
              key={c.id}
              className={`p-3 rounded-lg cursor-pointer transition-colors ${selected?.id === c.id ? 'bg-primary/10 border border-primary/30' : 'hover:bg-gray-50 border border-transparent'}`}
              onClick={() => handleSelectCadence(c)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{c.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {c.step_count} 步驟 · {c.enrollment_count} 名單
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-red-400 opacity-0 group-hover:opacity-100 flex-shrink-0"
                  onClick={e => { e.stopPropagation(); handleDelete(c.id) }}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Right: Cadence detail */}
      <main className="flex-1 overflow-y-auto">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            選擇左側 Cadence 查看詳情
          </div>
        ) : (
          <div className="p-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h1 className="text-xl font-bold">{selected.name}</h1>
                {selected.description && (
                  <p className="text-muted-foreground text-sm mt-1">{selected.description}</p>
                )}
              </div>
              <Button onClick={openEnroll}>
                <Plus className="w-4 h-4 mr-1.5" /> 加入名單
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* Timeline */}
              <div className="bg-white border rounded-xl p-5">
                <h3 className="font-semibold mb-4">波段時間軸</h3>
                {selected.steps && selected.steps.length > 0 ? (
                  <StepTimeline steps={selected.steps} />
                ) : (
                  <p className="text-sm text-muted-foreground">尚未設定步驟</p>
                )}
              </div>

              {/* Enrollments */}
              <div className="bg-white border rounded-xl p-5">
                <h3 className="font-semibold mb-4">加入名單 ({enrollments.length})</h3>
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {enrollments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">尚未加入任何名單</p>
                  ) : enrollments.map(e => (
                    <EnrollmentRow
                      key={e.id}
                      enrollment={e}
                      onAdvance={() => handleAdvance(e.id)}
                      onSkip={() => handleSkip(e.id)}
                      onPause={() => handlePause(e.id)}
                      onResume={() => handleResume(e.id)}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Create Cadence Modal */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        {showCreate && <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>建立 Cadence</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>名稱 *</Label>
              <Input value={formName} onChange={e => setFormName(e.target.value)} className="mt-1" placeholder="例：7天初次開發序列" />
            </div>
            <div>
              <Label>描述</Label>
              <Textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={2} className="mt-1" />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>步驟設定</Label>
                <Button size="sm" variant="outline" onClick={addStep}>
                  <Plus className="w-3.5 h-3.5 mr-1" /> 新增步驟
                </Button>
              </div>
              <div className="space-y-3">
                {formSteps.map((step, i) => (
                  <div key={i} className="border rounded-lg p-3 bg-gray-50">
                    <div className="grid grid-cols-12 gap-2 items-start">
                      <div className="col-span-2">
                        <Label className="text-xs">天數</Label>
                        <Input
                          type="number"
                          min={1}
                          value={step.day}
                          onChange={e => updateStep(i, { day: parseInt(e.target.value) || 1 })}
                          className="h-8 text-sm mt-0.5"
                        />
                      </div>
                      <div className="col-span-3">
                        <Label className="text-xs">類型</Label>
                        <Select value={step.type} onValueChange={v => updateStep(i, { type: v as CadenceStepType })}>
                          <SelectTrigger className="h-8 text-sm mt-0.5">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {STEP_TYPE_OPTIONS.map(opt => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      {step.type === 'email' && (
                        <div className="col-span-4">
                          <Label className="text-xs">模板（選填）</Label>
                          <Select value={step.template_id || '__none__'} onValueChange={v => updateStep(i, { template_id: v === '__none__' ? null : v })}>
                            <SelectTrigger className="h-8 text-sm mt-0.5">
                              <SelectValue placeholder="不選模板" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__none__">不選模板</SelectItem>
                              {templates.map(t => (
                                <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                      <div className="col-span-1 flex justify-end pt-5">
                        <Button size="sm" variant="ghost" className="h-8 w-8 p-0 text-red-400" onClick={() => removeStep(i)}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                      <div className="col-span-12">
                        <Label className="text-xs">備注</Label>
                        <Input
                          value={step.note || ''}
                          onChange={e => updateStep(i, { note: e.target.value })}
                          className="h-8 text-sm mt-0.5"
                          placeholder="說明此步驟的操作..."
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={loading || !formName.trim()}>
                {loading ? '建立中...' : '建立 Cadence'}
              </Button>
            </div>
          </div>
        </DialogContent>}
      </Dialog>

      {/* Enroll Leads Modal */}
      <Dialog open={showEnroll} onOpenChange={setShowEnroll}>
        {showEnroll && <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>加入名單到 {selected?.name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">已選擇 {selectedLeads.length} 筆名單</p>
            <div className="space-y-1 max-h-96 overflow-y-auto border rounded-lg p-2">
              {leads.map(lead => (
                <label key={lead.id} className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedLeads.includes(lead.id)}
                    onChange={e => {
                      if (e.target.checked) {
                        setSelectedLeads(s => [...s, lead.id])
                      } else {
                        setSelectedLeads(s => s.filter(id => id !== lead.id))
                      }
                    }}
                  />
                  <span className="text-sm flex-1">{lead.company_name}</span>
                  <span className="text-xs text-muted-foreground">{lead.contact_name}</span>
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowEnroll(false)}>取消</Button>
              <Button onClick={handleEnroll} disabled={loading || selectedLeads.length === 0}>
                {loading ? '加入中...' : `加入 ${selectedLeads.length} 筆`}
              </Button>
            </div>
          </div>
        </DialogContent>}
      </Dialog>
    </div>
  )
}
