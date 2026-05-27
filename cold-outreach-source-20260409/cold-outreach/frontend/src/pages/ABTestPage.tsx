import { useState, useEffect } from 'react'
import { getABTests, createABTest, getABTestResults, updateABTest } from '@/lib/api'
import { ABTest, ABTestResult } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Plus, BarChart3, Trophy } from 'lucide-react'
import { format } from 'date-fns'

export default function ABTestPage() {
  const [tests, setTests] = useState<ABTest[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [selectedResult, setSelectedResult] = useState<ABTestResult | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    name: '',
    subject_a: '',
    body_a: '',
    subject_b: '',
    body_b: '',
  })

  const loadTests = async () => {
    const res = await getABTests()
    setTests(res.data)
  }

  useEffect(() => { loadTests() }, [])

  const handleCreate = async () => {
    if (!form.name.trim() || !form.subject_a.trim() || !form.subject_b.trim()) return
    setCreating(true)
    try {
      await createABTest(form as Record<string, unknown>)
      setShowCreate(false)
      setForm({ name: '', subject_a: '', body_a: '', subject_b: '', body_b: '' })
      await loadTests()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '建立失敗')
    } finally {
      setCreating(false)
    }
  }

  const handleViewResult = async (test: ABTest) => {
    const res = await getABTestResults(test.id)
    setSelectedResult(res.data)
  }

  const handleComplete = async (test: ABTest) => {
    await updateABTest(test.id, { status: 'completed' })
    await loadTests()
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">A/B 測試</h1>
          <p className="text-sm text-muted-foreground mt-1">測試不同主旨/內文，找出最高回覆率的版本</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-1" /> 新增測試
        </Button>
      </div>

      <div className="space-y-4">
        {tests.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground border rounded-lg bg-white">
            <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p>尚無 A/B 測試</p>
            <p className="text-xs mt-1">建立第一個測試，對比不同信件版本的效果</p>
          </div>
        ) : tests.map(test => (
          <div key={test.id} className="border rounded-lg p-5 bg-white">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{test.name}</h3>
                  <Badge variant={test.status === 'completed' ? 'outline' : 'default'} className="text-xs">
                    {test.status === 'completed' ? '已完成' : '進行中'}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  建立於 {format(new Date(test.created_at), 'yyyy/MM/dd')}
                </p>
                <div className="grid grid-cols-2 gap-4 mt-3">
                  <div className="bg-blue-50 rounded p-3">
                    <p className="text-xs font-medium text-blue-700 mb-1">版本 A</p>
                    <p className="text-sm font-medium truncate">{test.subject_a}</p>
                    <p className="text-xs text-muted-foreground mt-1">已發送：{test.sent_a} 封</p>
                  </div>
                  <div className="bg-purple-50 rounded p-3">
                    <p className="text-xs font-medium text-purple-700 mb-1">版本 B</p>
                    <p className="text-sm font-medium truncate">{test.subject_b}</p>
                    <p className="text-xs text-muted-foreground mt-1">已發送：{test.sent_b} 封</p>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Button variant="outline" size="sm" onClick={() => handleViewResult(test)}>
                  <BarChart3 className="w-3.5 h-3.5 mr-1" /> 查看結果
                </Button>
                {test.status === 'running' && (
                  <Button variant="outline" size="sm" onClick={() => handleComplete(test)}>
                    標記完成
                  </Button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Create Modal */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-2xl max-h-screen overflow-y-auto">
          <DialogHeader><DialogTitle>新增 A/B 測試</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>測試名稱</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="例如：主旨測試 2026-03" className="mt-1" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-blue-700">版本 A</h3>
                <div>
                  <Label>主旨</Label>
                  <Input value={form.subject_a} onChange={e => setForm(f => ({ ...f, subject_a: e.target.value }))} className="mt-1" placeholder="版本 A 主旨..." />
                </div>
                <div>
                  <Label>內文</Label>
                  <Textarea value={form.body_a} onChange={e => setForm(f => ({ ...f, body_a: e.target.value }))} className="mt-1 h-36" placeholder="版本 A 內文..." />
                </div>
              </div>
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-purple-700">版本 B</h3>
                <div>
                  <Label>主旨</Label>
                  <Input value={form.subject_b} onChange={e => setForm(f => ({ ...f, subject_b: e.target.value }))} className="mt-1" placeholder="版本 B 主旨..." />
                </div>
                <div>
                  <Label>內文</Label>
                  <Textarea value={form.body_b} onChange={e => setForm(f => ({ ...f, body_b: e.target.value }))} className="mt-1 h-36" placeholder="版本 B 內文..." />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={creating || !form.name.trim() || !form.subject_a.trim() || !form.subject_b.trim()}>
                {creating ? '建立中...' : '建立測試'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Results Modal */}
      {selectedResult && (
        <Dialog open={true} onOpenChange={() => setSelectedResult(null)}>
          <DialogContent className="max-w-xl">
            <DialogHeader><DialogTitle>測試結果：{selectedResult.test.name}</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {(['a', 'b'] as const).map(variant => {
                  const data = selectedResult[variant]
                  const isWinner = selectedResult.winner?.toLowerCase() === variant
                  return (
                    <div key={variant} className={`border rounded-lg p-4 ${isWinner ? 'border-green-400 bg-green-50' : ''}`}>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className={`font-semibold ${variant === 'a' ? 'text-blue-700' : 'text-purple-700'}`}>
                          版本 {variant.toUpperCase()}
                        </h3>
                        {isWinner && (
                          <Badge className="bg-green-500 text-white text-xs flex items-center gap-1">
                            <Trophy className="w-3 h-3" /> Winner
                          </Badge>
                        )}
                      </div>
                      <div className="space-y-3">
                        <StatBar label="已發送" value={data.sent} max={Math.max(selectedResult.a.sent, selectedResult.b.sent)} unit="封" color={variant === 'a' ? 'bg-blue-400' : 'bg-purple-400'} />
                        <StatBar label="開信率" value={data.open_rate} max={100} unit="%" color={variant === 'a' ? 'bg-blue-500' : 'bg-purple-500'} />
                        <StatBar label="回覆率" value={data.reply_rate} max={100} unit="%" color={variant === 'a' ? 'bg-blue-600' : 'bg-purple-600'} />
                      </div>
                    </div>
                  )
                })}
              </div>
              {selectedResult.winner && (
                <p className="text-center text-sm font-medium text-green-700">
                  🏆 版本 {selectedResult.winner} 效果更好！建議使用此版本繼續發送。
                </p>
              )}
              {!selectedResult.winner && (
                <p className="text-center text-sm text-muted-foreground">兩個版本效果相當，需要更多數據。</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

function StatBar({ label, value, max, unit, color }: { label: string; value: number; max: number; unit: string; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value}{unit}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
