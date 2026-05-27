import { useState, useEffect, useCallback } from 'react'
import { getDueSteps, advanceEnrollment, skipStep, sendEmail, getGmailAuthUrl } from '@/lib/api'
import { CadenceEnrollment, CadenceStepType } from '@/types'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { CheckCircle, SkipForward, RefreshCw, Mail } from 'lucide-react'

const STEP_ICONS: Record<CadenceStepType, string> = {
  email: '📧',
  call: '📞',
  linkedin: '🔗',
  sms: '💬',
}

const STEP_LABELS: Record<CadenceStepType, string> = {
  email: 'Email',
  call: '電話',
  linkedin: 'LinkedIn',
  sms: 'SMS',
}

export default function TodayPage() {
  const [dueItems, setDueItems] = useState<CadenceEnrollment[]>([])
  const [loading, setLoading] = useState(true)
  const [completing, setCompleting] = useState<Record<string, boolean>>({})

  // Email compose
  const [showEmailModal, setShowEmailModal] = useState(false)
  const [currentEnrollment, setCurrentEnrollment] = useState<CadenceEnrollment | null>(null)
  const [emailTo, setEmailTo] = useState('')
  const [emailSubject, setEmailSubject] = useState('')
  const [emailBody, setEmailBody] = useState('')
  const [sendingEmail, setSendingEmail] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getDueSteps()
      setDueItems(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleComplete = async (enrollment: CadenceEnrollment) => {
    const stepInfo = enrollment.current_step_info
    if (stepInfo?.type === 'email') {
      setCurrentEnrollment(enrollment)
      setEmailTo(enrollment.email || '')
      setEmailSubject(stepInfo.subject || `跟進 — ${enrollment.company_name}`)
      setEmailBody('')
      setShowEmailModal(true)
    } else {
      setCompleting(c => ({ ...c, [enrollment.id]: true }))
      try {
        await advanceEnrollment(enrollment.id)
        await load()
      } finally {
        setCompleting(c => ({ ...c, [enrollment.id]: false }))
      }
    }
  }

  const handleSkip = async (enrollmentId: string) => {
    setCompleting(c => ({ ...c, [enrollmentId]: true }))
    try {
      await skipStep(enrollmentId)
      await load()
    } finally {
      setCompleting(c => ({ ...c, [enrollmentId]: false }))
    }
  }

  const handleSendAndComplete = async () => {
    if (!currentEnrollment) return
    setSendingEmail(true)
    try {
      await sendEmail({
        lead_id: currentEnrollment.lead_id,
        to: emailTo,
        subject: emailSubject,
        body: emailBody,
      })
      await advanceEnrollment(currentEnrollment.id)
      setShowEmailModal(false)
      await load()
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

  const grouped = dueItems.reduce((acc, item) => {
    const type = item.current_step_info?.type || 'unknown'
    if (!acc[type]) acc[type] = []
    acc[type].push(item)
    return acc
  }, {} as Record<string, CadenceEnrollment[]>)

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">📅 今日待辦</h1>
          <p className="text-muted-foreground text-sm mt-1">
            共 {dueItems.length} 件需要處理
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
          重新整理
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground">載入中...</div>
      ) : dueItems.length === 0 ? (
        <div className="text-center py-16 bg-white border rounded-xl">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
          <p className="text-lg font-medium text-gray-700">今日所有任務完成！</p>
          <p className="text-sm text-muted-foreground mt-1">目前沒有需要處理的 Cadence 步驟</p>
        </div>
      ) : (
        <div className="space-y-6">
          {(Object.entries(grouped) as [CadenceStepType, CadenceEnrollment[]][]).map(([type, items]) => (
            <div key={type}>
              <h2 className="font-semibold mb-3 flex items-center gap-2">
                <span>{STEP_ICONS[type] || '📋'}</span>
                <span>{STEP_LABELS[type] || type} ({items.length})</span>
              </h2>
              <div className="space-y-3">
                {items.map(item => (
                  <div key={item.id} className="bg-white border rounded-xl p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium">{item.company_name}</span>
                          <span className="text-xs text-muted-foreground">·</span>
                          <span className="text-sm text-muted-foreground">{item.contact_name}</span>
                        </div>
                        {item.email && (
                          <p className="text-xs text-muted-foreground">{item.email}</p>
                        )}
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                            {item.cadence_name}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            步驟 {item.current_step + 1}/{item.total_steps}
                          </span>
                        </div>
                        {item.current_step_info?.note && (
                          <p className="text-sm text-gray-600 mt-2 bg-gray-50 rounded-lg p-2">
                            {item.current_step_info.note}
                          </p>
                        )}
                        {item.next_action_at && (
                          <p className="text-xs text-orange-500 mt-1">
                            到期：{new Date(item.next_action_at).toLocaleString('zh-TW')}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-col gap-1.5 flex-shrink-0">
                        <Button
                          size="sm"
                          className="h-8"
                          onClick={() => handleComplete(item)}
                          disabled={completing[item.id]}
                        >
                          {type === 'email' ? (
                            <><Mail className="w-3.5 h-3.5 mr-1.5" /> 發信</>
                          ) : (
                            <><CheckCircle className="w-3.5 h-3.5 mr-1.5" /> 完成</>
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-gray-500"
                          onClick={() => handleSkip(item.id)}
                          disabled={completing[item.id]}
                        >
                          <SkipForward className="w-3.5 h-3.5 mr-1" /> 跳過
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Email Modal */}
      <Dialog open={showEmailModal} onOpenChange={setShowEmailModal}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>發送 Email — {currentEnrollment?.company_name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>收件人</Label>
              <Input value={emailTo} onChange={e => setEmailTo(e.target.value)} className="mt-1" />
            </div>
            <div>
              <Label>主旨</Label>
              <Input value={emailSubject} onChange={e => setEmailSubject(e.target.value)} className="mt-1" />
            </div>
            <div>
              <Label>內文</Label>
              <Textarea value={emailBody} onChange={e => setEmailBody(e.target.value)} rows={8} className="mt-1" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowEmailModal(false)}>取消</Button>
              <Button onClick={handleSendAndComplete} disabled={sendingEmail}>
                {sendingEmail ? '發送中...' : '發送並完成步驟'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
