import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import { getSalesPerformance, getUsers } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { SalesPerformance, User, LEAD_STATUS_LABELS, LeadStatus } from '@/types'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { TrendingUp, Mail, Target, Award } from 'lucide-react'

function MetricCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div className={`rounded-xl p-4 ${color}`}>
      <p className="text-xs font-medium opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs opacity-60 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function SalesPerformancePage() {
  const { user } = useAuth()
  const [perf, setPerf] = useState<SalesPerformance | null>(null)
  const [loading, setLoading] = useState(true)
  const [users, setUsers] = useState<User[]>([])
  const [selectedUserId, setSelectedUserId] = useState<string>('me')

  const load = useCallback(async (uid?: string) => {
    setLoading(true)
    try {
      const res = await getSalesPerformance(uid)
      setPerf(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    if (user?.role === 'admin') {
      getUsers().then(r => setUsers(r.data)).catch(() => {})
    }
  }, [load, user])

  const handleUserChange = (uid: string) => {
    setSelectedUserId(uid)
    load(uid === 'me' ? undefined : uid)
  }

  if (loading) return <div className="p-6 text-muted-foreground">載入中...</div>
  if (!perf) return <div className="p-6 text-muted-foreground">無法載入績效資料</div>

  // Compare this week vs last week
  const weeks = perf.weekly
  const thisWeek = weeks[weeks.length - 1]
  const lastWeek = weeks[weeks.length - 2]
  const emailDelta = thisWeek && lastWeek ? thisWeek.emails_sent - lastWeek.emails_sent : 0

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">業務績效</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {perf.user.name} 的績效報告
          </p>
        </div>
        {user?.role === 'admin' && (
          <Select value={selectedUserId} onValueChange={handleUserChange}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="選擇業務" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="me">我自己</SelectItem>
              {users.map(u => (
                <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label="總名單"
          value={perf.totals.total_leads}
          color="bg-indigo-50 text-indigo-700"
        />
        <MetricCard
          label="總發信"
          value={perf.totals.total_emails}
          sub={`本週 ${thisWeek?.emails_sent || 0} 封 (${emailDelta >= 0 ? '+' : ''}${emailDelta})`}
          color="bg-blue-50 text-blue-700"
        />
        <MetricCard
          label="回覆率"
          value={`${perf.totals.reply_rate}%`}
          sub={`${perf.totals.total_replied} 筆已回覆`}
          color="bg-yellow-50 text-yellow-700"
        />
        <MetricCard
          label="成交率"
          value={`${perf.totals.win_rate}%`}
          sub={`${perf.totals.total_won} 筆成交`}
          color="bg-green-50 text-green-700"
        />
      </div>

      {/* Weekly trend chart */}
      <div className="bg-white border rounded-xl p-5">
        <h2 className="font-semibold text-sm mb-4 flex items-center gap-1.5">
          <TrendingUp className="w-4 h-4 text-indigo-500" />
          最近 8 週趨勢
        </h2>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={perf.weekly}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="emails_sent"
              name="發信數"
              stroke="#6366f1"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="replies"
              name="回覆數"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="won"
              name="成交數"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* This week vs last week */}
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold text-sm mb-4 flex items-center gap-1.5">
            <Mail className="w-4 h-4 text-blue-500" />
            本週 vs 上週
          </h2>
          <div className="space-y-3">
            {[
              { label: '發信數', thisVal: thisWeek?.emails_sent || 0, lastVal: lastWeek?.emails_sent || 0 },
              { label: '回覆數', thisVal: thisWeek?.replies || 0, lastVal: lastWeek?.replies || 0 },
              { label: '成交數', thisVal: thisWeek?.won || 0, lastVal: lastWeek?.won || 0 },
            ].map(({ label, thisVal, lastVal }) => {
              const delta = thisVal - lastVal
              return (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium w-8 text-right">{thisVal}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${delta >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {delta >= 0 ? '+' : ''}{delta}
                    </span>
                    <span className="text-xs text-muted-foreground w-12 text-right">上週 {lastVal}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Top scored leads */}
        <div className="bg-white border rounded-xl p-5">
          <h2 className="font-semibold text-sm mb-4 flex items-center gap-1.5">
            <Award className="w-4 h-4 text-yellow-500" />
            最高分名單 Top 5
          </h2>
          {perf.top_leads.length === 0 ? (
            <p className="text-sm text-muted-foreground">尚無評分名單</p>
          ) : (
            <div className="space-y-2">
              {perf.top_leads.map((lead, i) => (
                <div key={lead.id} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-4">{i + 1}.</span>
                    <span className="text-sm font-medium">{lead.company_name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      lead.score >= 80 ? 'bg-green-100 text-green-700' :
                      lead.score >= 50 ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-500'
                    }`}>{lead.score}</span>
                    <span className="text-xs text-muted-foreground">
                      {LEAD_STATUS_LABELS[lead.status as LeadStatus] || lead.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
