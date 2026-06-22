import { useState } from 'react'
import {
  ragicGetExistingClients,
  ragicGetNewClients,
  ragicUpsertNewClient,
  RagicRow,
} from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Search, Plus, ExternalLink, RefreshCw, Building2, UserRound } from 'lucide-react'

type TableKind = 'existing' | 'new'

const EMPTY_NEW = {
  company_name: '',
  client_contact: '',
  phone: '',
  am: '',
  email: '',
  website: '',
  industry: '',
  title: '',
  mobile: '',
  department: '',
  client_department: '',
  remark: '',
}

export default function RagicPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<TableKind>('existing')

  // 共用查詢狀態
  const [query, setQuery] = useState({
    company_name: '', am: '', client_contact: '',
    tax_id: '', client_department: '',
    email: '', phone: '',
  })
  const [rows, setRows] = useState<RagicRow[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  // 新增/更新 modal
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_NEW, am: user?.name || '' })
  const [saving, setSaving] = useState(false)

  const handleSearch = async () => {
    setLoading(true)
    setSearched(true)
    try {
      if (tab === 'existing') {
        const res = await ragicGetExistingClients({
          company_name: query.company_name || undefined,
          tax_id: query.tax_id || undefined,
          am: query.am || undefined,
          client_contact: query.client_contact || undefined,
          client_department: query.client_department || undefined,
        })
        setRows(res.data.data || [])
      } else {
        const res = await ragicGetNewClients({
          company_name: query.company_name || undefined,
          am: query.am || undefined,
          client_contact: query.client_contact || undefined,
          email: query.email || undefined,
          phone: query.phone || undefined,
        })
        setRows(res.data.data || [])
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '查詢失敗')
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  const openAdd = () => {
    setForm({ ...EMPTY_NEW, am: user?.name || '' })
    setShowAdd(true)
  }

  const handleSave = async () => {
    if (!form.company_name || !form.client_contact || !form.phone || !form.am) {
      alert('公司名稱、聯絡人、電話、接洽人為必填')
      return
    }
    setSaving(true)
    try {
      const res = await ragicUpsertNewClient(form)
      const mode = res.data.data.mode === 'add' ? '新增' : '更新'
      alert(`${mode}成功（Ragic ID: ${res.data.data.ragic_data_id}）`)
      setShowAdd(false)
      if (tab === 'new') handleSearch()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '寫入失敗')
    } finally {
      setSaving(false)
    }
  }

  const switchTab = (k: TableKind) => {
    setTab(k)
    setRows([])
    setSearched(false)
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold">Ragic 中台查詢</h1>
          <p className="text-sm text-muted-foreground mt-1">查詢既有客戶 / 陌生開發名單，或新增資料至陌開表</p>
        </div>
        <Button onClick={openAdd}>
          <Plus className="w-4 h-4 mr-1" /> 新增到陌開表
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b mt-6">
        {([
          { k: 'existing' as const, label: '既有客戶表', icon: <Building2 className="w-4 h-4" /> },
          { k: 'new' as const, label: '陌生開發表', icon: <UserRound className="w-4 h-4" /> },
        ]).map(t => (
          <button
            key={t.k}
            onClick={() => switchTab(t.k)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.k ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* 查詢條件 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-5">
        <div>
          <Label className="text-xs">公司名稱</Label>
          <Input
            value={query.company_name}
            onChange={e => setQuery(q => ({ ...q, company_name: e.target.value }))}
            placeholder="包含關鍵字即可"
            className="mt-1"
            onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
          />
        </div>
        <div>
          <Label className="text-xs">接洽人 / 業務</Label>
          <Input
            value={query.am}
            onChange={e => setQuery(q => ({ ...q, am: e.target.value }))}
            placeholder="王、Amy…"
            className="mt-1"
            onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
          />
        </div>
        <div>
          <Label className="text-xs">聯絡人</Label>
          <Input
            value={query.client_contact}
            onChange={e => setQuery(q => ({ ...q, client_contact: e.target.value }))}
            className="mt-1"
            onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
          />
        </div>
        {tab === 'existing' ? (
          <>
            <div>
              <Label className="text-xs">統一編號</Label>
              <Input
                value={query.tax_id}
                onChange={e => setQuery(q => ({ ...q, tax_id: e.target.value }))}
                className="mt-1"
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
              />
            </div>
            <div>
              <Label className="text-xs">客戶窗口部門</Label>
              <Input
                value={query.client_department}
                onChange={e => setQuery(q => ({ ...q, client_department: e.target.value }))}
                className="mt-1"
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
              />
            </div>
          </>
        ) : (
          <>
            <div>
              <Label className="text-xs">Email</Label>
              <Input
                value={query.email}
                onChange={e => setQuery(q => ({ ...q, email: e.target.value }))}
                className="mt-1"
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
              />
            </div>
            <div>
              <Label className="text-xs">電話</Label>
              <Input
                value={query.phone}
                onChange={e => setQuery(q => ({ ...q, phone: e.target.value }))}
                className="mt-1"
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
              />
            </div>
          </>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <Button onClick={handleSearch} disabled={loading}>
          {loading ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Search className="w-4 h-4 mr-1" />}
          查詢
        </Button>
        {searched && (
          <div className="flex items-center text-sm text-muted-foreground ml-2">
            共 {rows.length} 筆
          </div>
        )}
      </div>

      {/* 結果 */}
      {searched && (
        <div className="mt-5 border rounded-lg bg-white overflow-x-auto">
          {rows.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              {loading ? '查詢中...' : '查無資料'}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr className="text-left text-xs font-medium text-muted-foreground">
                  <th className="py-2 px-3">公司</th>
                  <th className="py-2 px-3">聯絡人</th>
                  <th className="py-2 px-3">接洽人</th>
                  <th className="py-2 px-3">電話</th>
                  <th className="py-2 px-3">Email</th>
                  <th className="py-2 px-3">官網</th>
                  <th className="py-2 px-3">狀態</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r._ragicId} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium">{r.公司}</td>
                    <td className="py-2 px-3">{r.聯絡人 || '—'}</td>
                    <td className="py-2 px-3">{r.接洽人 || '—'}</td>
                    <td className="py-2 px-3">{r.電話 || '—'}</td>
                    <td className="py-2 px-3">{r.Email || '—'}</td>
                    <td className="py-2 px-3">
                      {r.官網 ? (
                        <a href={r.官網.startsWith('http') ? r.官網 : `https://${r.官網}`}
                          target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-1 text-blue-600 hover:underline">
                          連結 <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : '—'}
                    </td>
                    <td className="py-2 px-3">{r.狀態 || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* 新增/更新 Modal */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>新增 / 更新 陌開表</DialogTitle></DialogHeader>
          <p className="text-xs text-muted-foreground -mt-2">
            以「公司名稱」精準比對：已存在則更新，不存在則新增。
          </p>
          <div className="grid grid-cols-2 gap-3 mt-2">
            <div>
              <Label className="text-xs">公司名稱 *</Label>
              <Input value={form.company_name} onChange={e => setForm(f => ({ ...f, company_name: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">接洽人 *</Label>
              <Input value={form.am} onChange={e => setForm(f => ({ ...f, am: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">聯絡人 *</Label>
              <Input value={form.client_contact} onChange={e => setForm(f => ({ ...f, client_contact: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">電話 *</Label>
              <Input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">Email</Label>
              <Input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">手機</Label>
              <Input value={form.mobile} onChange={e => setForm(f => ({ ...f, mobile: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">職稱</Label>
              <Input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">產業</Label>
              <Input value={form.industry} onChange={e => setForm(f => ({ ...f, industry: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">公司網站</Label>
              <Input value={form.website} onChange={e => setForm(f => ({ ...f, website: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">負責單位</Label>
              <Input value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">聯絡窗口部門</Label>
              <Input value={form.client_department} onChange={e => setForm(f => ({ ...f, client_department: e.target.value }))} className="mt-1" />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">備註</Label>
              <Input value={form.remark} onChange={e => setForm(f => ({ ...f, remark: e.target.value }))} className="mt-1" />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowAdd(false)}>取消</Button>
            <Button onClick={handleSave} disabled={saving}>{saving ? '寫入中...' : '寫入 Ragic'}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
