import { useState, useEffect } from 'react'
import { generateWeeklyReport, getWeeklyReportHistory, getWeeklyReport } from '@/lib/api'
import { WeeklyReport } from '@/types'
import { Button } from '@/components/ui/button'
import { FileText, RefreshCw, Printer, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { format } from 'date-fns'
import { zhTW } from 'date-fns/locale'

export default function WeeklyReportPage() {
  const [currentReport, setCurrentReport] = useState<WeeklyReport | null>(null)
  const [history, setHistory] = useState<Omit<WeeklyReport, 'content'>[]>([])
  const [generating, setGenerating] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null)

  const loadHistory = async () => {
    setLoadingHistory(true)
    try {
      const res = await getWeeklyReportHistory()
      setHistory(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingHistory(false)
    }
  }

  useEffect(() => { loadHistory() }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await generateWeeklyReport()
      setCurrentReport(Array.isArray(res.data) ? res.data : [])
      setSelectedHistoryId(null)
      await loadHistory()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '生成失敗')
    } finally {
      setGenerating(false)
    }
  }

  const handleLoadHistory = async (id: string) => {
    try {
      const res = await getWeeklyReport(id)
      setCurrentReport(Array.isArray(res.data) ? res.data : [])
      setSelectedHistoryId(id)
    } catch {
      alert('載入失敗')
    }
  }

  const handleExportPdf = () => {
    if (!currentReport) return
    // Open PDF export in new window and auto-print
    const url = `/api/reports/weekly/export_pdf?report_id=${currentReport.id}`
    window.open(url, '_blank')
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">AI 週報</h1>
          <p className="text-sm text-muted-foreground mt-1">自動生成銷售週報，分析本週表現與建議</p>
        </div>
        <div className="flex gap-2">
          {currentReport && (
            <Button variant="outline" onClick={handleExportPdf}>
              <Printer className="w-4 h-4 mr-1" /> 匯出 PDF
            </Button>
          )}
          <Button onClick={handleGenerate} disabled={generating}>
            {generating ? (
              <><RefreshCw className="w-4 h-4 mr-1 animate-spin" /> 生成中...</>
            ) : (
              <><RefreshCw className="w-4 h-4 mr-1" /> 生成本週週報</>
            )}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* History sidebar */}
        <div className="col-span-1">
          <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wider">歷史週報</h2>
          <div className="space-y-2">
            {loadingHistory ? (
              <p className="text-xs text-muted-foreground">載入中...</p>
            ) : history.length === 0 ? (
              <p className="text-xs text-muted-foreground">尚無歷史週報</p>
            ) : history.map(h => (
              <button
                key={h.id}
                onClick={() => handleLoadHistory(h.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  selectedHistoryId === h.id ? 'bg-primary text-primary-foreground' : 'bg-white border hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 opacity-50" />
                  <span className="font-medium">
                    {format(new Date(h.week_start), 'MM/dd', { locale: zhTW })} - {format(new Date(h.week_end), 'MM/dd', { locale: zhTW })}
                  </span>
                </div>
                <p className={`text-xs mt-0.5 ${selectedHistoryId === h.id ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                  {format(new Date(h.created_at), 'yyyy/MM/dd')}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Report content */}
        <div className="col-span-3">
          {!currentReport ? (
            <div className="border rounded-lg bg-white p-12 text-center">
              <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <h3 className="text-lg font-medium text-gray-600 mb-2">尚無週報</h3>
              <p className="text-sm text-muted-foreground mb-6">點擊「生成本週週報」按鈕，AI 將自動分析本週銷售數據並生成報告</p>
              <Button onClick={handleGenerate} disabled={generating}>
                {generating ? '生成中...' : '生成本週週報'}
              </Button>
            </div>
          ) : (
            <div className="border rounded-lg bg-white p-6">
              {/* Stats summary */}
              {currentReport.stats && (
                <div className="grid grid-cols-4 gap-3 mb-6 pb-6 border-b">
                  {[
                    { label: '發信', value: currentReport.stats.this_week?.emails_sent ?? 0, prev: currentReport.stats.last_week?.emails_sent ?? 0, unit: '封' },
                    { label: '回覆', value: currentReport.stats.this_week?.replied ?? 0, prev: currentReport.stats.last_week?.replied ?? 0, unit: '筆' },
                    { label: '成交', value: currentReport.stats.this_week?.won ?? 0, prev: currentReport.stats.last_week?.won ?? 0, unit: '筆' },
                    { label: '新名單', value: currentReport.stats.this_week?.new_leads ?? 0, prev: currentReport.stats.last_week?.new_leads ?? 0, unit: '筆' },
                  ].map(stat => {
                    const delta = stat.value - stat.prev
                    return (
                      <div key={stat.label} className="text-center">
                        <p className="text-2xl font-bold">{stat.value}</p>
                        <p className="text-xs text-muted-foreground">{stat.label}</p>
                        <p className={`text-xs mt-0.5 font-medium ${delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-500' : 'text-gray-400'}`}>
                          {delta > 0 ? `+${delta}` : delta < 0 ? `${delta}` : '0'} vs 上週
                        </p>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Markdown content */}
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown>{currentReport.content}</ReactMarkdown>
              </div>

              <p className="text-xs text-muted-foreground mt-6 pt-4 border-t">
                生成時間：{format(new Date(currentReport.created_at), 'yyyy/MM/dd HH:mm')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
