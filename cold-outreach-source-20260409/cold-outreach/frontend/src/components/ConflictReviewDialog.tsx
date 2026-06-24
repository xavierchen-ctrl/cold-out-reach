import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { AlertTriangle, Loader2 } from 'lucide-react'
import type { ImportConflict } from '@/lib/api'

type Action = 'approve' | 'skip'

export default function ConflictReviewDialog({
  open,
  conflicts,
  newCount,
  loading,
  onCancel,
  onConfirm,
}: {
  open: boolean
  conflicts: ImportConflict[]
  newCount: number
  loading: boolean
  onCancel: () => void
  onConfirm: (actions: Record<string, Action>) => void
}) {
  const [actions, setActions] = useState<Record<string, Action>>({})

  // 預設全部「不匯入」
  useEffect(() => {
    if (open) {
      const init: Record<string, Action> = {}
      conflicts.forEach(c => { init[c.company_name] = 'skip' })
      setActions(init)
    }
  }, [open, conflicts])

  const setAll = (a: Action) => {
    const next: Record<string, Action> = {}
    conflicts.forEach(c => { next[c.company_name] = a })
    setActions(next)
  }

  const approveCount = Object.values(actions).filter(a => a === 'approve').length
  const skipCount = conflicts.length - approveCount

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onCancel() }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            偵測到 {conflicts.length} 家相似的名單
          </DialogTitle>
        </DialogHeader>

        <p className="text-sm text-muted-foreground">
          以下要匯入的公司與系統現有名單相似（同名 / 同統編 / 同網域）。
          請逐筆決定：<span className="font-medium">不匯入</span> 或 <span className="font-medium">送審核</span>。
          {newCount > 0 && <>另有 <span className="font-medium text-green-700">{newCount}</span> 家全新名單會直接匯入。</>}
        </p>

        {/* 批次操作 */}
        <div className="flex items-center gap-2 border-y py-2">
          <span className="text-xs text-muted-foreground">批次：</span>
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setAll('skip')}>全部不匯入</Button>
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setAll('approve')}>全部送審核</Button>
          <span className="ml-auto text-xs text-muted-foreground">送審 {approveCount}、不匯入 {skipCount}</span>
        </div>

        {/* 衝突清單 */}
        <div className="space-y-2">
          {conflicts.map(c => {
            const act = actions[c.company_name] || 'skip'
            return (
              <div key={c.company_name} className="border rounded-lg p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{c.company_name}</p>
                    <p className="text-xs text-amber-700 mt-0.5">{c.reason}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      系統現有：{c.matched_company}
                      {c.matched_department ? `（${c.matched_department}）` : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 rounded-md border overflow-hidden text-xs">
                    <button
                      className={`px-3 py-1.5 transition-colors ${act === 'skip' ? 'bg-gray-200 font-medium' : 'bg-white hover:bg-gray-50'}`}
                      onClick={() => setActions(p => ({ ...p, [c.company_name]: 'skip' }))}
                    >
                      不匯入
                    </button>
                    <button
                      className={`px-3 py-1.5 transition-colors border-l ${act === 'approve' ? 'bg-blue-600 text-white font-medium' : 'bg-white hover:bg-gray-50'}`}
                      onClick={() => setActions(p => ({ ...p, [c.company_name]: 'approve' }))}
                    >
                      送審核
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div className="flex justify-end gap-2 border-t pt-3">
          <Button variant="outline" onClick={onCancel} disabled={loading}>取消</Button>
          <Button onClick={() => onConfirm(actions)} disabled={loading}>
            {loading ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" />匯入中...</> : '確認匯入'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
