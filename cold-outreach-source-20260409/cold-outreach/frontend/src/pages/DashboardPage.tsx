import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { getStatsOverview, getStatsBySales, getStatsFunnel, getStatsTrend, getStaleLeads, getAiSuggestions, getPipelineHealthCached, exportExcel, getBestTime, generateWeeklyReport, getCampaignSummary } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { Sparkles, RefreshCw, AlertTriangle, Download, Activity, Clock, FileBarChart2, TrendingUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BestTime, WeeklyReport, CampaignSummary } from '@/types'

const STATUS_LABELS: Record<string, string> = {
  new: '新名單', contacted: '已接觸', replied: '已回覆',
  meeting_scheduled: '已約訪', won: '已成交', lost: '已流失',
}
const FUNNEL_COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#10b981', '#ef4444']

export default function DashboardPage() {
  const { user } = useAuth()
  const [overview, setOverview] = useState<Record<string, number> | null>(null)
  const [salesStats, setSalesStats] = useState<any[]>([])
  const [funnel, setFunnel] = useState<any[]>([])
  const [trend, setTrend] = useState<any[]>([])
  const [stale, setStale] = useState<any[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [pipelineHealth, setPipelineHealth] = useState<string>('')
  const [loadingHealth, setLoadingHealth] = useState(false)
  const [loading, setLoading] = useState(true)
  const [bestTimes, setBestTimes] = useState<BestTime[]>([])
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null)
  const [campaignSummary, setCampaignSummary] = useState<CampaignSummary | null>(null)

  useEffect(() => { loadAll() }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [ov, fn, tr, st] = await Promise.all([
        getStatsOverview(),
        getStatsFunnel(),
        getStatsTrend(),
        getStaleLeads(),
      ])
      setOverview(ov.data)
      setFunnel(fn.data.map((f: any, i: number) => ({
        ...f, label: STATUS_LABELS[f.status] || f.status, fill: FUNNEL_COLORS[i],
      })))
      setTrend(tr.data)
      setStale(st.data)

      if (user?.role === 'admin') {
        const ss = await getStatsBySales()
        setSalesStats(ss.data)
      }

      // Load AI suggestions
      loadSuggestions()
      loadPipelineHealth()

      // Load best times and weekly report
      getBestTime().then(r => setBestTimes(r.data)).catch(() => {})
      generateWeeklyReport().then(r => setWeeklyReport(r.data)).catch(() => {})
      getCampaignSummary().then(r => setCampaignSummary(r.data)).catch(() => {})
    } finally {
      setLoading(false)
    }
  }

  const loadSuggestions = async (refresh = false) => {
    setLoadingSuggestions(true)
    try {
      const res = await getAiSuggestions(refresh)
      setSuggestions(res.data.suggestions)
    } catch {
      setSuggestions(['無法取得 AI 建議，請確認 Gemini API Key 設定'])
    } finally {
      setLoadingSuggestions(false)
    }
  }

  const loadPipelineHealth = async (refresh = false) => {
    setLoadingHealth(true)
    try {
      const res = await getPipelineHealthCached(refresh)
      setPipelineHealth(res.data.report)
    } catch {
      setPipelineHealth('無法載入 Pipeline 健診，請確認 Gemini API Key 設定')
    } finally {
      setLoadingHealth(false)
    }
  }

  const handleExportExcel = async () => {
    try {
      const res = await exportExcel()
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `cold_outreach_${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('匯出失敗')
    }
  }

  if (loading) return <div className="p-6 text-muted-foreground">載入中...</div>

  return (
    <div className="p-3 md:p-6 space-y-4 md:space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <Button variant="outline" size="sm" onClick={handleExportExcel}>
          <Download className="w-4 h-4 mr-1.5" /> 匯出 Excel
        </Button>
      </div>

      {/* Overview cards */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: '總名單', value: overview.total_leads, color: 'bg-indigo-50 text-indigo-700' },
            { label: '本週發信', value: overview.emails_sent_this_week, color: 'bg-purple-50 text-purple-700' },
            { label: '已成交', value: overview.won, color: 'bg-green-50 text-green-700' },
            { label: '已約訪', value: overview.meeting_scheduled, color: 'bg-pink-50 text-pink-700' },
          ].map(card => (
            <div key={card.label} className={`rounded-xl p-4 ${card.color}`}>
              <p className="text-xs font-medium opacity-70">{card.label}</p>
              <p className="text-3xl font-bold mt-1">{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Best Time + Weekly Report row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Best sending times */}
        <div className="bg-white border rounded-xl p-4">
          <h2 className="font-semibold text-sm mb-3 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-blue-500" /> 最佳發信時段
          </h2>
          {bestTimes.length === 0 ? (
            <p className="text-xs text-muted-foreground">發送更多郵件後，將顯示最佳時段分析</p>
          ) : (
            <div className="space-y-2">
              {bestTimes.map((bt, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className={`text-lg font-bold ${i === 0 ? 'text-amber-500' : i === 1 ? 'text-gray-400' : 'text-amber-700'}`}>
                    #{i + 1}
                  </span>
                  <div className="flex-1">
                    <span className="text-sm font-medium">{bt.day_name} {bt.hour_label}</span>
                    <p className="text-xs text-muted-foreground">發送 {bt.sent_count} 封</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    i === 0 ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {i === 0 ? '🥇 最佳' : i === 1 ? '🥈 次佳' : '🥉 第三'}
                  </span>
                </div>
              ))}
            </div>
          )}
          <a href="/analytics" className="text-xs text-blue-500 hover:underline mt-3 block">查看完整熱力圖 →</a>
        </div>

        {/* Weekly report preview */}
        <div className="bg-white border rounded-xl p-4">
          <h2 className="font-semibold text-sm mb-3 flex items-center gap-1.5">
            <FileBarChart2 className="w-4 h-4 text-purple-500" /> 本週週報
          </h2>
          {!weeklyReport ? (
            <p className="text-xs text-muted-foreground">正在生成週報...</p>
          ) : (
            <div>
              {weeklyReport.stats && (
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    { label: '發信', value: weeklyReport.stats.this_week?.emails_sent ?? 0 },
                    { label: '回覆', value: weeklyReport.stats.this_week?.replied ?? 0 },
                    { label: '成交', value: weeklyReport.stats.this_week?.won ?? 0 },
                    { label: '新名單', value: weeklyReport.stats.this_week?.new_leads ?? 0 },
                  ].map(s => (
                    <div key={s.label} className="text-center bg-gray-50 rounded p-2">
                      <p className="text-lg font-bold">{s.value}</p>
                      <p className="text-xs text-muted-foreground">{s.label}</p>
                    </div>
                  ))}
                </div>
              )}
              <div className="text-xs text-gray-600 line-clamp-3 prose prose-xs">
                <ReactMarkdown>{weeklyReport.content?.slice(0, 300) + '...'}</ReactMarkdown>
              </div>
              <a href="/reports" className="text-xs text-purple-500 hover:underline mt-2 block">查看完整週報 →</a>
            </div>
          )}
        </div>
      </div>

      {/* Engagement Funnel */}
      {campaignSummary && (
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold text-sm mb-4 flex items-center gap-1.5">
            <Activity className="w-4 h-4 text-blue-500" /> 互動漏斗
          </h2>
          <div className="flex items-end gap-2 flex-wrap">
            {[
              { label: '發信', value: campaignSummary.emails_sent, color: 'bg-blue-100 text-blue-700' },
              { label: '開信', value: campaignSummary.opened, color: 'bg-indigo-100 text-indigo-700', rate: campaignSummary.open_rate },
              { label: '點擊', value: campaignSummary.clicked, color: 'bg-purple-100 text-purple-700', rate: campaignSummary.click_rate },
              { label: '回覆', value: campaignSummary.replied, color: 'bg-pink-100 text-pink-700', rate: campaignSummary.reply_rate },
              { label: '會議', value: campaignSummary.meeting_scheduled, color: 'bg-green-100 text-green-700' },
            ].map((stage, i, arr) => (
              <div key={stage.label} className="flex items-center gap-2">
                <div className={`rounded-lg p-3 text-center min-w-[72px] ${stage.color}`}>
                  <p className="text-2xl font-bold">{stage.value}</p>
                  <p className="text-xs font-medium">{stage.label}</p>
                  {stage.rate && <p className="text-xs opacity-70 mt-0.5">{stage.rate}</p>}
                </div>
                {i < arr.length - 1 && (
                  <span className="text-gray-300 text-lg">→</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend chart */}
        <div className="lg:col-span-2 bg-white border rounded-xl p-5">
          <h2 className="font-semibold text-sm mb-4">最近 14 天趨勢</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="new_leads" name="新增名單" stroke="#6366f1" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="emails_sent" name="發信數" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* AI suggestions */}
        <div className="bg-white border rounded-xl p-5 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-purple-500" /> 今日 AI 建議
            </h2>
            <Button variant="ghost" size="sm" onClick={() => loadSuggestions(true)} disabled={loadingSuggestions}>
              <RefreshCw className={`w-3.5 h-3.5 ${loadingSuggestions ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          {loadingSuggestions ? (
            <p className="text-sm text-muted-foreground">生成中...</p>
          ) : (
            <ul className="space-y-2 flex-1">
              {suggestions.map((s, i) => (
                <li key={i} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-purple-400 mt-0.5 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Funnel chart */}
      <div className="bg-white border rounded-xl p-5">
        <h2 className="font-semibold text-sm mb-4">Pipeline 漏斗</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={funnel} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis dataKey="label" type="category" tick={{ fontSize: 11 }} width={60} />
            <Tooltip />
            <Bar dataKey="count" name="數量" radius={[0, 4, 4, 0]}>
              {funnel.map((entry, i) => (
                <rect key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Sales leaderboard (admin only) */}
      {user?.role === 'admin' && salesStats.length > 0 && (
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold text-sm mb-4">業務排行</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/50">
                <tr>
                  <th className="px-4 py-2 text-left">業務</th>
                  <th className="px-4 py-2 text-right">名單數</th>
                  <th className="px-4 py-2 text-right">已接觸</th>
                  <th className="px-4 py-2 text-right">接觸率</th>
                  <th className="px-4 py-2 text-right">已回覆</th>
                  <th className="px-4 py-2 text-right">回覆率</th>
                  <th className="px-4 py-2 text-right">成交</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {salesStats.map((s: any, i) => (
                  <tr key={s.user_id} className={i === 0 ? 'font-medium' : ''}>
                    <td className="px-4 py-2">
                      {i === 0 && <span className="text-yellow-500 mr-1">🏆</span>}
                      {s.name}
                    </td>
                    <td className="px-4 py-2 text-right">{s.total}</td>
                    <td className="px-4 py-2 text-right">{s.contacted}</td>
                    <td className="px-4 py-2 text-right">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${s.contact_rate >= 50 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                        {s.contact_rate}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">{s.replied}</td>
                    <td className="px-4 py-2 text-right">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${s.reply_rate >= 30 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                        {s.reply_rate}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-semibold text-green-600">{s.won}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pipeline Health */}
      <div className="bg-white border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-sm flex items-center gap-1.5">
            <Activity className="w-4 h-4 text-indigo-500" /> Pipeline 健診
          </h2>
          <Button variant="ghost" size="sm" onClick={() => loadPipelineHealth(true)} disabled={loadingHealth}>
            <RefreshCw className={`w-3.5 h-3.5 ${loadingHealth ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        {loadingHealth ? (
          <p className="text-sm text-muted-foreground">分析中...</p>
        ) : pipelineHealth ? (
          <div className="prose prose-sm max-w-none text-sm">
            <ReactMarkdown>{pipelineHealth}</ReactMarkdown>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">點擊重新分析以載入健診報告</p>
        )}
      </div>

      {/* Stale leads warning */}
      {stale.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
          <h2 className="font-semibold text-sm text-amber-800 flex items-center gap-1.5 mb-3">
            <AlertTriangle className="w-4 h-4" /> 超過 7 天未跟進（{stale.length} 筆）
          </h2>
          <div className="space-y-2">
            {stale.slice(0, 5).map((lead: any) => (
              <div key={lead.id} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <span className="font-medium">{lead.company_name}</span>
                  <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">
                    {STATUS_LABELS[lead.status] || lead.status}
                  </span>
                </div>
                <span className="text-xs text-amber-600 font-medium">
                  已 {lead.days_stale} 天
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
