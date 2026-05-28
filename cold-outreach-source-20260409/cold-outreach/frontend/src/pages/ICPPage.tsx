import { useState, useEffect } from 'react'
import { ICPProfile } from '@/types'
import { getICPs, createICP, updateICP, deleteICP } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Plus, Pencil, Trash2, Target } from 'lucide-react'

const EMPTY_FORM = {
  name: '',
  industries: '',
  company_sizes: '',
  titles: '',
  locations: '',
}

function parseArr(val: string): string[] {
  return val.split(/[,、\n]/).map(s => s.trim()).filter(Boolean)
}
function arrToStr(arr: string[]): string {
  return arr.join('、')
}

export default function ICPPage() {
  const [profiles, setProfiles] = useState<ICPProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<ICPProfile | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await getICPs()
      setProfiles(Array.isArray(res.data) ? res.data : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (p: ICPProfile) => {
    setEditing(p)
    setForm({
      name: p.name,
      industries: arrToStr(p.industries),
      company_sizes: arrToStr(p.company_sizes),
      titles: arrToStr(p.titles),
      locations: arrToStr(p.locations),
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        industries: parseArr(form.industries),
        company_sizes: parseArr(form.company_sizes),
        titles: parseArr(form.titles),
        locations: parseArr(form.locations),
      }
      if (editing) {
        await updateICP(editing.id, payload)
      } else {
        await createICP(payload)
      }
      setShowModal(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此 ICP？')) return
    await deleteICP(id)
    load()
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Target className="w-5 h-5" /> ICP 理想客戶輪廓
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">定義目標客戶條件，套用至爬蟲自動篩選</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="w-4 h-4 mr-1.5" /> 新增 ICP
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">載入中...</p>
      ) : profiles.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Target className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-lg">尚無 ICP 設定</p>
          <p className="text-sm mt-1">建立 ICP 以快速套用爬蟲篩選條件</p>
          <Button className="mt-4" onClick={openCreate}>
            <Plus className="w-4 h-4 mr-1.5" /> 建立第一個 ICP
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles.map(p => (
            <div key={p.id} className="bg-white border rounded-xl p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-base">{p.name}</h3>
                <div className="flex gap-1">
                  <button onClick={() => openEdit(p)} className="p-1.5 text-muted-foreground hover:text-primary rounded">
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => handleDelete(p.id)} className="p-1.5 text-muted-foreground hover:text-destructive rounded">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="space-y-2 text-sm">
                {p.industries.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-muted-foreground">目標產業</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {p.industries.map(i => (
                        <span key={i} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{i}</span>
                      ))}
                    </div>
                  </div>
                )}
                {p.company_sizes.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-muted-foreground">公司規模</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {p.company_sizes.map(s => (
                        <span key={s} className="px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                {p.titles.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-muted-foreground">目標職稱</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {p.titles.map(t => (
                        <span key={t} className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded text-xs">{t}</span>
                      ))}
                    </div>
                  </div>
                )}
                {p.locations.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-muted-foreground">地區</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {p.locations.map(l => (
                        <span key={l} className="px-1.5 py-0.5 bg-orange-50 text-orange-700 rounded text-xs">{l}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                建立於 {new Date(p.created_at).toLocaleDateString('zh-TW')}
              </p>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <Dialog open onOpenChange={setShowModal}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{editing ? '編輯 ICP' : '新增 ICP'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>名稱 *</Label>
                <Input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="例：台灣中型電商品牌"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>目標產業 <span className="text-muted-foreground font-normal text-xs">（逗號分隔）</span></Label>
                <Input
                  value={form.industries}
                  onChange={e => setForm(f => ({ ...f, industries: e.target.value }))}
                  placeholder="例：電商、數位行銷、零售"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>公司規模 <span className="text-muted-foreground font-normal text-xs">（逗號分隔）</span></Label>
                <Input
                  value={form.company_sizes}
                  onChange={e => setForm(f => ({ ...f, company_sizes: e.target.value }))}
                  placeholder="例：50-200、200-500"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>目標職稱 <span className="text-muted-foreground font-normal text-xs">（逗號分隔）</span></Label>
                <Input
                  value={form.titles}
                  onChange={e => setForm(f => ({ ...f, titles: e.target.value }))}
                  placeholder="例：行銷長、數位行銷主管、CMO"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>地區 <span className="text-muted-foreground font-normal text-xs">（逗號分隔）</span></Label>
                <Input
                  value={form.locations}
                  onChange={e => setForm(f => ({ ...f, locations: e.target.value }))}
                  placeholder="例：台北、新北、台中"
                  className="mt-1"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setShowModal(false)}>取消</Button>
                <Button onClick={handleSave} disabled={saving || !form.name.trim()}>
                  {saving ? '儲存中...' : '儲存'}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
