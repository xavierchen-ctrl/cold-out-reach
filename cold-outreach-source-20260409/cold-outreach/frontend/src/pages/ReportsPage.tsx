import { useState, useEffect, useCallback } from 'react'
import {
  getCampaignSummary, exportDeliveryExcel, getMonthlyPdf,
  getCadences, getCadenceEnrollments,
} from '@/lib/api'
import { CampaignSummary, Cadence, CadenceEnrollment } from '@/types'
import { Button } from '@/components/ui/button'
import { Download, FileBarChart2, TrendingUp, Mail, MousePointer, MessageSquare, Calendar, RefreshCw } from 'lucide-react'

function MetricCard({ icon, label, value, sub }: {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <div className="bg-white border rounded-xl p-5 flex items-start gap-4">
      <div className="p-2 bg-primary/10 rounded-lg text-primary">{icon}</div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-sm font-medium text-gray-700 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function FunnelBar({ label, value, total, color }: {
  label: string
  value: number
  total: number
  color: string
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-sm text-muted-foreground">{value} ({pct}%)</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-3">
        <div
          className={`h-3 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

interface CadenceStats {
  cadence: Cadence
  enrollments: CadenceEnrollment[]
  completed: number
  completion_rate: number
}

export default function ReportsPage() {
  const [summary, setSummary] = useState<CampaignSummary | null>(null)
  const [cadenceStats, setCadenceStats] = useState<CadenceStats[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [summaryRes, cadencesRes] = await Promise.all([
        getCampaignSummary(),
        getCadences(),
      ])
      setSummary(summaryRes.data)

      // Load enrollments for each cadence
      const cadenceList: Cadence[] = cadencesRes.data
      const statsPromises = cadenceList.slice(0, 10).map(async (c) => {
        const res = await getCadenceEnrollments(c.id)
        const enrollments: CadenceEnrollment[] = res.data
        const completed = enrollments.filter(e => e.status === 'completed').length
        const completion_rate = enrollments.length > 0
          ? Math.round((completed / enrollments.length) * 100)
          : 0
        return { cadence: c, enrollments, completed, completion_rate }
      })
      const stats = await Promise.all(statsPromises)
      setCadenceStats(stats)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleDownloadExcel = async () => {
    setDownloading(true)
    try {
      const res = await exportDeliveryExcel()
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `delivery_report_${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  const handleMonthlyPdf = async () => {
    const res = await getMonthlyPdf()
    const newWindow = window.open()
    if (newWindow) {
      newWindow.document.write(res.data)
      newWindow.document.close()
    }
  }

  if (loading) {
    return <div className="p-6 text-muted-foreground">載入中...</div>
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">📊 報告中心</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            重新整理
          </Button>
          <Button variant="outline" onClick={handleMonthlyPdf}>
            <FileBarChart2 className="w-4 h-4 mr-1.5" /> 月報 PDF
          </Button>
          <Button onClick={handleDownloadExcel} disabled={downloading}>
            <Download className="w-4 h-4 mr-1.5" />
            {downloading ? '下載中...' : '下載名單交付 Excel'}
          </Button>
        </div>
      </div>

      {/* Campaign Summary */}
      {summary && (
        <>
          <div>
            <h2 className="font-semibold text-lg mb-3">活動成效摘要</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <MetricCard
                icon={<Mail className="w-5 h-5" />}
                label="發信總數"
                value={summary.emails_sent}
              />
              <MetricCard
                icon={<TrendingUp className="w-5 h-5" />}
                label="開信率"
                value={summary.open_rate}
                sub={`${summary.opened} 次開信`}
              />
              <MetricCard
                icon={<MousePointer className="w-5 h-5" />}
                label="點擊率"
                value={summary.click_rate}
                sub={`${summary.clicked} 次點擊`}
              />
              <MetricCard
                icon={<MessageSquare className="w-5 h-5" />}
                label="回覆率"
                value={summary.reply_rate}
                sub={`${summary.replied} 筆回覆`}
              />
              <MetricCard
                icon={<Calendar className="w-5 h-5" />}
                label="會議確認"
                value={summary.meeting_scheduled}
              />
            </div>
          </div>

          {/* Funnel */}
          <div className="bg-white border rounded-xl p-5">
            <h2 className="font-semibold mb-4">互動漏斗</h2>
            <div className="max-w-2xl">
              <FunnelBar
                label="📋 總名單"
                value={summary.total_leads}
                total={summary.total_leads}
                color="bg-gray-400"
              />
              <FunnelBar
                label="✉️ 已接觸"
                value={summary.contacted}
                total={summary.total_leads}
                color="bg-blue-400"
              />
              <FunnelBar
                label="👁️ 開信"
                value={summary.opened}
                total={summary.total_leads}
                color="bg-indigo-400"
              />
              <FunnelBar
                label="🖱️ 點擊"
                value={summary.clicked}
                total={summary.total_leads}
                color="bg-purple-400"
              />
              <FunnelBar
                label="💬 回覆"
                value={summary.replied}
                total={summary.total_leads}
                color="bg-pink-400"
              />
              <FunnelBar
                label="📅 會議"
                value={summary.meeting_scheduled}
                total={summary.total_leads}
                color="bg-green-400"
              />
            </div>

            {/* Conversion rates between stages */}
            {summary.emails_sent > 0 && (
              <div className="mt-4 pt-4 border-t grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="text-center">
                  <p className="text-lg font-bold text-primary">{summary.contact_rate}</p>
                  <p className="text-xs text-muted-foreground">接觸率</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-primary">{summary.open_rate}</p>
                  <p className="text-xs text-muted-foreground">開信率</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-primary">{summary.click_rate}</p>
                  <p className="text-xs text-muted-foreground">點擊率</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-primary">{summary.reply_rate}</p>
                  <p className="text-xs text-muted-foreground">回覆率</p>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Cadence Stats */}
      {cadenceStats.length > 0 && (
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold mb-4">🎯 Cadence 波段統計</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 font-medium text-muted-foreground">Cadence 名稱</th>
                  <th className="text-center py-2 font-medium text-muted-foreground">步驟數</th>
                  <th className="text-center py-2 font-medium text-muted-foreground">加入名單</th>
                  <th className="text-center py-2 font-medium text-muted-foreground">進行中</th>
                  <th className="text-center py-2 font-medium text-muted-foreground">已完成</th>
                  <th className="text-left py-2 font-medium text-muted-foreground">完成率</th>
                </tr>
              </thead>
              <tbody>
                {cadenceStats.map(({ cadence, enrollments, completed, completion_rate }) => {
                  const active = enrollments.filter(e => e.status === 'active').length
                  return (
                    <tr key={cadence.id} className="border-b hover:bg-gray-50">
                      <td className="py-3 font-medium">{cadence.name}</td>
                      <td className="py-3 text-center">{cadence.step_count}</td>
                      <td className="py-3 text-center">{enrollments.length}</td>
                      <td className="py-3 text-center">
                        <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{active}</span>
                      </td>
                      <td className="py-3 text-center">
                        <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full">{completed}</span>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-gray-100 rounded-full h-2 max-w-[100px]">
                            <div
                              className="bg-primary h-2 rounded-full"
                              style={{ width: `${completion_rate}%` }}
                            />
                          </div>
                          <span className="text-muted-foreground text-xs">{completion_rate}%</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
