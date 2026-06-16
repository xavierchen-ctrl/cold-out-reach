import { useState, useEffect } from 'react'
import { getHeatmap, getBestTime, getKeywordTrackers, createKeywordTracker, deleteKeywordTracker, checkKeywords } from '@/lib/api'
import { HeatmapRow, BestTime, KeywordTracker } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Plus, Search, Trash2, Clock, CheckCircle, XCircle, RefreshCw } from 'lucide-react'

const DAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']

function getHeatColor(rate: number): string {
  if (rate === 0) return '#f1f5f9'
  if (rate < 10) return '#bfdbfe'
  if (rate < 20) return '#60a5fa'
  if (rate < 30) return '#2563eb'
  return '#1e3a8a'
}

function getHeatTextColor(rate: number): string {
  return rate >= 20 ? '#fff' : '#1e293b'
}

export default function AnalyticsPage() {
  const [heatmap, setHeatmap] = useState<HeatmapRow[]>([])
  const [bestTimes, setBestTimes] = useState<BestTime[]>([])
  const [trackers, setTrackers] = useState<KeywordTracker[]>([])
  const [showCreateTracker, setShowCreateTracker] = useState(false)
  const [newTrackerUrl, setNewTrackerUrl] = useState('')
  const [newTrackerKeywords, setNewTrackerKeywords] = useState('')
  const [newTrackerLeadId, setNewTrackerLeadId] = useState('')
  const [creating, setCreating] = useState(false)
  const [checking, setChecking] = useState<string | null>(null)
  const [hoveredCell, setHoveredCell] = useState<{ day: number; hour: number } | null>(null)
  const [tooltip, setTooltip] = useState<{ sent: number; replied: number; reply_rate: number } | null>(null)

  const loadData = async () => {
    try {
      const [hm, bt, kt] = await Promise.all([getHeatmap(), getBestTime(), getKeywordTrackers()])
      setHeatmap(hm.data)
      setBestTimes(bt.data)
      setTrackers(kt.data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { loadData() }, [])

  const handleCreateTracker = async () => {
    const keywords = newTrackerKeywords.split(/[,，\n]/).map(k => k.trim()).filter(Boolean)
    if (!newTrackerUrl.trim() || keywords.length === 0) return
    setCreating(true)
    try {
      await createKeywordTracker({
        website_url: newTrackerUrl.trim(),
        keywords,
        lead_id: newTrackerLeadId.trim() || null,
      })
      setShowCreateTracker(false)
      setNewTrackerUrl('')
      setNewTrackerKeywords('')
      setNewTrackerLeadId('')
      await loadData()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '建立失敗')
    } finally {
      setCreating(false)
    }
  }

  const handleCheck = async (id: string) => {
    setChecking(id)
    try {
      await checkKeywords(id)
      await loadData()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '檢測失敗')
    } finally {
      setChecking(null)
    }
  }

  const handleDeleteTracker = async (id: string) => {
    if (!confirm('確定刪除此監測設定？')) return
    await deleteKeywordTracker(id)
    await loadData()
  }

  const handleCellHover = (row: HeatmapRow, cell: { day: number; hour: number; sent: number; replied: number; reply_rate: number }) => {
    setHoveredCell({ day: cell.day, hour: cell.hour })
    setTooltip({ sent: cell.sent, replied: cell.replied, reply_rate: cell.reply_rate })
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">智能分析</h1>

      {/* Heatmap Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">📊 發信熱力圖</h2>
          {bestTimes.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-muted-foreground">最佳時段：</span>
              {bestTimes.map((bt, i) => (
                <span key={i} className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full font-medium">
                  <Clock className="w-3 h-3" />
                  {DAY_LABELS[bt.day]}曜 {bt.hour_label}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white border rounded-lg p-4 overflow-x-auto">
          {heatmap.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">載入中...</div>
          ) : (
            <div>
              {/* Hour labels */}
              <div className="flex">
                <div className="w-12 flex-shrink-0" />
                {Array.from({ length: 24 }, (_, h) => (
                  <div key={h} className="w-8 flex-shrink-0 text-center text-xs text-muted-foreground py-1">
                    {h % 3 === 0 ? `${h}` : ''}
                  </div>
                ))}
              </div>

              {heatmap.map((row, dayIdx) => (
                <div key={dayIdx} className="flex items-center">
                  <div className="w-12 flex-shrink-0 text-xs text-muted-foreground font-medium text-right pr-2">
                    {DAY_LABELS[dayIdx]}
                  </div>
                  {row.hours.map((cell) => (
                    <div
                      key={cell.hour}
                      className="w-8 h-7 flex-shrink-0 m-0.5 rounded cursor-pointer relative transition-transform hover:scale-110"
                      style={{
                        backgroundColor: getHeatColor(cell.reply_rate),
                      }}
                      onMouseEnter={() => handleCellHover(row, cell)}
                      onMouseLeave={() => { setHoveredCell(null); setTooltip(null) }}
                    />
                  ))}
                </div>
              ))}

              {/* Legend */}
              <div className="flex items-center gap-2 mt-3 justify-end">
                <span className="text-xs text-muted-foreground">回覆率：低</span>
                {[0, 5, 15, 25, 35].map(rate => (
                  <div key={rate} className="w-5 h-4 rounded" style={{ backgroundColor: getHeatColor(rate) }} />
                ))}
                <span className="text-xs text-muted-foreground">高</span>
              </div>

              {/* Tooltip */}
              {tooltip && hoveredCell && (
                <div className="mt-2 text-xs bg-gray-800 text-white px-3 py-2 rounded inline-block">
                  {DAY_LABELS[hoveredCell.day]}曜 {hoveredCell.hour.toString().padStart(2, '0')}:00 —
                  發信 {tooltip.sent} 封，回覆 {tooltip.replied} 封，回覆率 {tooltip.reply_rate}%
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Keyword Trackers Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">競品關鍵字追蹤</h2>
          <Button size="sm" onClick={() => setShowCreateTracker(true)}>
            <Plus className="w-4 h-4 mr-1" /> 新增監測
          </Button>
        </div>

        <div className="space-y-3">
          {trackers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm border rounded-lg bg-white">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>尚無關鍵字監測設定</p>
            </div>
          ) : trackers.map(tracker => (
            <div key={tracker.id} className="border rounded-lg p-4 bg-white">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{tracker.website_url}</p>
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {(tracker.keywords || []).map(kw => (
                      <span key={kw} className="text-xs bg-gray-100 px-2 py-0.5 rounded">{kw}</span>
                    ))}
                  </div>
                  {tracker.last_checked && (
                    <p className="text-xs text-muted-foreground mt-1">
                      上次檢測：{new Date(tracker.last_checked).toLocaleString('zh-TW')}
                    </p>
                  )}
                  {tracker.last_result && (
                    <div className="mt-2 space-y-1">
                      {Object.entries(tracker.last_result).map(([kw, result]) => (
                        <div key={kw} className="flex items-start gap-2 text-xs">
                          {result.found ? (
                            <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0 mt-0.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                          )}
                          <div>
                            <span className="font-medium">{kw}</span>
                            {result.found && result.context && (
                              <p className="text-muted-foreground mt-0.5 line-clamp-1">「{result.context}」</p>
                            )}
                            {!result.found && <span className="text-muted-foreground ml-1">— 未找到</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-1 ml-3">
                  <Button variant="outline" size="sm" onClick={() => handleCheck(tracker.id)} disabled={checking === tracker.id}>
                    {checking === tracker.id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3.5 h-3.5" />
                    )}
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleDeleteTracker(tracker.id)} className="text-red-500">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Create Tracker Modal */}
      <Dialog open={showCreateTracker} onOpenChange={setShowCreateTracker}>
        <DialogContent>
          <DialogHeader><DialogTitle>新增關鍵字監測</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>網站 URL</Label>
              <Input value={newTrackerUrl} onChange={e => setNewTrackerUrl(e.target.value)} placeholder="https://example.com" className="mt-1" />
            </div>
            <div>
              <Label>關鍵字（逗號分隔）</Label>
              <Input value={newTrackerKeywords} onChange={e => setNewTrackerKeywords(e.target.value)} placeholder="SEO, 數位行銷, 電商" className="mt-1" />
            </div>
            <div>
              <Label>關聯名單 ID（選填）</Label>
              <Input value={newTrackerLeadId} onChange={e => setNewTrackerLeadId(e.target.value)} placeholder="Lead UUID" className="mt-1" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreateTracker(false)}>取消</Button>
              <Button onClick={handleCreateTracker} disabled={creating || !newTrackerUrl.trim() || !newTrackerKeywords.trim()}>
                {creating ? '建立中...' : '建立'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
