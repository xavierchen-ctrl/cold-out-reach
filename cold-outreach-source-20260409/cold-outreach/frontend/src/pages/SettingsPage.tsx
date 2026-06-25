import { useState, useEffect } from 'react'
import { getTags, createTag, deleteTag, getUsers, createUser, updateUser, deleteUser, getTeams, createTeam, updateTeam, deleteTeam, changePassword, getGmailAuthUrl, getGmailStatus, disconnectGmail, getManagerScope } from '@/lib/api'
import { Tag, User as UserType, Team } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Trash2, Plus, Tag as TagIcon, User, Users, Eye, EyeOff, Mail, CheckCircle2, XCircle } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

function PasswordInput({ value, onChange, placeholder, className }: {
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  className?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <Input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={className}
      />
      <button
        type="button"
        onClick={() => setShow(v => !v)}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-gray-700"
        tabIndex={-1}
      >
        {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  )
}

const PRESET_COLORS = [
  '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
  '#8b5cf6', '#ef4444', '#06b6d4', '#84cc16', '#f97316',
]

type SettingsTab = 'tags' | 'profile' | 'users' | 'teams'

export default function SettingsPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<SettingsTab>('tags')

  const tabs = [
    { key: 'tags', label: '標籤管理', icon: TagIcon },
    { key: 'profile', label: '個人資料', icon: User },
    ...(user?.role === 'admin' ? [
      { key: 'users', label: '帳號管理', icon: Users },
      { key: 'teams', label: '部門管理', icon: Users },
    ] : []),
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">設定</h1>
      <div className="flex gap-1 mb-6 border-b flex-wrap">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key as SettingsTab)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === key ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-gray-700'
            }`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>
      {tab === 'tags' && <TagsTab />}
      {tab === 'profile' && <ProfileTab />}
      {tab === 'users' && user?.role === 'admin' && <UsersTab currentUserId={user.id} />}
      {tab === 'teams' && user?.role === 'admin' && <TeamsTab />}
    </div>
  )
}

// ── Tags Tab ──────────────────────────────────────────────────────────────────
function TagsTab() {
  const [tags, setTags] = useState<Tag[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(PRESET_COLORS[0])
  const [creating, setCreating] = useState(false)

  const loadTags = async () => {
    const res = await getTags()
    setTags(Array.isArray(res.data) ? res.data : [])
  }
  useEffect(() => { loadTags() }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await createTag({ name: newName.trim(), color: newColor })
      setNewName('')
      setNewColor(PRESET_COLORS[0])
      setShowCreate(false)
      await loadTags()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '建立失敗')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此標籤？相關名單的標籤也會一併移除。')) return
    await deleteTag(id)
    await loadTags()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">標籤管理</h2>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-1" /> 新增標籤
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {tags.map(tag => (
          <div key={tag.id} className="flex items-center justify-between p-3 border rounded-lg bg-white">
            <div className="flex items-center gap-2">
              <span className="w-4 h-4 rounded-full flex-shrink-0" style={{ backgroundColor: tag.color }} />
              <span className="text-sm font-medium">{tag.name}</span>
            </div>
            <button onClick={() => handleDelete(tag.id)} className="text-gray-400 hover:text-red-500 transition-colors">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
        {tags.length === 0 && (
          <div className="col-span-4 text-center py-8 text-muted-foreground text-sm">
            尚無標籤，點擊「新增標籤」開始建立
          </div>
        )}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader><DialogTitle>新增標籤</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>標籤名稱</Label>
              <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="例如：優先名單" className="mt-1" />
            </div>
            <div>
              <Label>顏色</Label>
              <div className="flex gap-2 mt-2 flex-wrap">
                {PRESET_COLORS.map(color => (
                  <button
                    key={color}
                    onClick={() => setNewColor(color)}
                    className={`w-7 h-7 rounded-full transition-transform ${newColor === color ? 'ring-2 ring-offset-2 ring-gray-400 scale-110' : ''}`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-sm text-muted-foreground">自訂：</span>
                <input type="color" value={newColor} onChange={e => setNewColor(e.target.value)} className="w-8 h-8 cursor-pointer rounded" />
                <span className="text-sm font-mono">{newColor}</span>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
                {creating ? '建立中...' : '建立'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Users Tab (Admin only) ────────────────────────────────────────────────────
const ROLE_LABELS: Record<string, string> = {
  admin: '管理員',
  manager: '主管',
  team_lead: '小組長',
  sales: '業務',
}

function UsersTab({ currentUserId }: { currentUserId: string }) {
  const [users, setUsers] = useState<UserType[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingUser, setEditingUser] = useState<UserType | null>(null)
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'sales' })
  const [editForm, setEditForm] = useState({ name: '', role: 'sales', password: '', team_id: '', manager_team_ids: [] as string[] })
  const [saving, setSaving] = useState(false)
  const [filterName, setFilterName] = useState('')
  const [filterEmail, setFilterEmail] = useState('')
  const [filterRole, setFilterRole] = useState('__all__')

  const loadData = async () => {
    try {
      const [uRes, tRes] = await Promise.all([getUsers(), getTeams()])
      setUsers(Array.isArray(uRes.data) ? uRes.data : [])
      setTeams(Array.isArray(tRes.data) ? tRes.data : [])
    } catch {}
  }
  useEffect(() => { loadData() }, [])

  const teamName = (id: string | null) => teams.find(t => t.id === id)?.name ?? '—'

  const filteredUsers = users.filter(u => {
    if (filterName && !u.name.toLowerCase().includes(filterName.toLowerCase())) return false
    if (filterEmail && !u.email.toLowerCase().includes(filterEmail.toLowerCase())) return false
    if (filterRole !== '__all__' && u.role !== filterRole) return false
    return true
  })

  const handleCreate = async () => {
    if (!form.name || !form.email || !form.password) return
    if (form.password.length < 8 || !/[a-zA-Z]/.test(form.password) || !/[0-9]/.test(form.password)) {
      alert('密碼需至少 8 碼，且必須包含英文字母與數字')
      return
    }
    setSaving(true)
    try {
      await createUser(form)
      setForm({ name: '', email: '', password: '', role: 'sales' })
      setShowCreate(false)
      await loadData()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '建立失敗')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingUser) return
    setSaving(true)
    try {
      const payload: { name?: string; role?: string; password?: string; team_id?: string | null; manager_team_ids?: string[] } = {
        name: editForm.name || undefined,
        role: editForm.role || undefined,
        team_id: editForm.team_id || null,
      }
      if (editForm.password) payload.password = editForm.password
      if (editForm.role === 'manager') payload.manager_team_ids = editForm.manager_team_ids
      await updateUser(editingUser.id, payload)
      setEditingUser(null)
      await loadData()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '更新失敗')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (user: UserType) => {
    if (user.id === currentUserId) { alert('無法刪除自己'); return }
    if (!confirm(`確定刪除帳號 ${user.name}（${user.email}）？`)) return
    try {
      await deleteUser(user.id)
      await loadData()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '刪除失敗')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">帳號管理</h2>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-1" /> 新增帳號
        </Button>
      </div>

      <div className="flex gap-2 mb-3 flex-wrap">
        <Input
          placeholder="搜尋姓名..."
          value={filterName}
          onChange={e => setFilterName(e.target.value)}
          className="w-40"
        />
        <Input
          placeholder="搜尋 Email..."
          value={filterEmail}
          onChange={e => setFilterEmail(e.target.value)}
          className="w-48"
        />
        <Select value={filterRole} onValueChange={setFilterRole}>
          <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">全部權限</SelectItem>
            <SelectItem value="sales">業務</SelectItem>
            <SelectItem value="team_lead">小組長</SelectItem>
            <SelectItem value="manager">主管</SelectItem>
            <SelectItem value="admin">管理員</SelectItem>
          </SelectContent>
        </Select>
        {(filterName || filterEmail || filterRole !== '__all__') && (
          <Button variant="outline" size="sm" onClick={() => { setFilterName(''); setFilterEmail(''); setFilterRole('__all__') }}>
            清除篩選
          </Button>
        )}
        <span className="text-sm text-muted-foreground self-center ml-auto">{filteredUsers.length} / {users.length} 人</span>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th className="px-4 py-3 text-left font-medium">姓名</th>
              <th className="px-4 py-3 text-left font-medium">Email</th>
              <th className="px-4 py-3 text-left font-medium">角色</th>
              <th className="px-4 py-3 text-left font-medium">部門</th>
              <th className="px-4 py-3 text-left font-medium">建立時間</th>
              <th className="px-4 py-3 text-left font-medium w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filteredUsers.map(u => (
              <tr key={u.id} className="hover:bg-muted/20">
                <td className="px-4 py-3 font-medium">
                  {u.name}
                  {u.id === currentUserId && <span className="ml-2 text-xs text-muted-foreground">（你）</span>}
                </td>
                <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                <td className="px-4 py-3">
                  <Badge variant={u.role === 'admin' ? 'default' : u.role === 'manager' ? 'outline' : 'secondary'} className="text-xs">
                    {ROLE_LABELS[u.role] || u.role}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{teamName(u.team_id)}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {new Date(u.created_at).toLocaleDateString('zh-TW')}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => {
                      setEditingUser(u)
                      setEditForm({ name: u.name, role: u.role, password: '', team_id: u.team_id ?? '', manager_team_ids: [] })
                      if (u.role === 'manager') {
                        getManagerScope(u.id).then(r => setEditForm(f => ({ ...f, manager_team_ids: r.data.team_ids || [] }))).catch(() => {})
                      }
                    }}>
                      ✏️
                    </Button>
                    {u.id !== currentUserId && (
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-500 hover:text-red-700" onClick={() => handleDelete(u)}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create Modal */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>新增帳號</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>姓名 *</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label>Email *</Label>
              <Input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label>密碼 *</Label>
              <PasswordInput value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label>角色</Label>
              <Select value={form.role} onValueChange={v => setForm(f => ({ ...f, role: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="sales">業務</SelectItem>
                  <SelectItem value="team_lead">小組長</SelectItem>
                  <SelectItem value="manager">主管</SelectItem>
                  <SelectItem value="admin">管理員</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={saving || !form.name || !form.email || !form.password}>
                {saving ? '建立中...' : '建立'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={!!editingUser} onOpenChange={() => setEditingUser(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>編輯帳號 — {editingUser?.name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>姓名</Label>
              <Input value={editForm.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label>角色</Label>
              <Select value={editForm.role} onValueChange={v => setEditForm(f => ({ ...f, role: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="sales">業務</SelectItem>
                  <SelectItem value="team_lead">小組長</SelectItem>
                  <SelectItem value="manager">主管</SelectItem>
                  <SelectItem value="admin">管理員</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>部門</Label>
              <Select value={editForm.team_id || '__none__'} onValueChange={v => setEditForm(f => ({ ...f, team_id: v === '__none__' ? '' : v }))}>
                <SelectTrigger className="mt-1"><SelectValue placeholder="不指定部門" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">不指定</SelectItem>
                  {teams.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {editForm.role === 'manager' && (
              <div>
                <Label>主管可管理的組 <span className="text-muted-foreground font-normal text-xs">（勾選的組成員名單此主管才看得到；不勾＝看全部）</span></Label>
                <div className="mt-1 border rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                  {teams.length === 0 ? (
                    <p className="text-xs text-muted-foreground">尚無部門，請先到「部門管理」建立組</p>
                  ) : teams.map(t => (
                    <label key={t.id} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        className="rounded"
                        checked={editForm.manager_team_ids.includes(t.id)}
                        onChange={e => setEditForm(f => ({
                          ...f,
                          manager_team_ids: e.target.checked
                            ? [...f.manager_team_ids, t.id]
                            : f.manager_team_ids.filter(x => x !== t.id),
                        }))}
                      />
                      {t.name}
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div>
              <Label>新密碼 <span className="text-muted-foreground font-normal text-xs">（留空表示不修改）</span></Label>
              <PasswordInput value={editForm.password} onChange={e => setEditForm(f => ({ ...f, password: e.target.value }))} className="mt-1" placeholder="不修改請留空" />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setEditingUser(null)}>取消</Button>
              <Button onClick={handleUpdate} disabled={saving}>
                {saving ? '儲存中...' : '儲存'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Teams Tab (Admin only) ────────────────────────────────────────────────────
function TeamsTab() {
  const [teams, setTeams] = useState<Team[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingTeam, setEditingTeam] = useState<Team | null>(null)
  const [newName, setNewName] = useState('')
  const [editName, setEditName] = useState('')
  const [saving, setSaving] = useState(false)
  const [memberCounts, setMemberCounts] = useState<Record<string, number>>({})

  const loadTeams = async () => {
    try {
      const res = await getTeams()
      const list: Team[] = Array.isArray(res.data) ? res.data : []
      setTeams(list)
      const uRes = await getUsers()
      const users: UserType[] = Array.isArray(uRes.data) ? uRes.data : []
      const counts: Record<string, number> = {}
      list.forEach(t => { counts[t.id] = users.filter(u => u.team_id === t.id).length })
      setMemberCounts(counts)
    } catch {}
  }
  useEffect(() => { loadTeams() }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setSaving(true)
    try {
      await createTeam({ name: newName.trim() })
      setNewName('')
      setShowCreate(false)
      await loadTeams()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '建立失敗')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingTeam || !editName.trim()) return
    setSaving(true)
    try {
      await updateTeam(editingTeam.id, { name: editName.trim() })
      setEditingTeam(null)
      await loadTeams()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '更新失敗')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (team: Team) => {
    if (!confirm(`確定刪除部門「${team.name}」？成員將不再屬於任何部門。`)) return
    try {
      await deleteTeam(team.id)
      await loadTeams()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '刪除失敗')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">部門管理</h2>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-1" /> 新增部門
        </Button>
      </div>

      <div className="space-y-3">
        {teams.map(t => (
          <div key={t.id} className="border rounded-lg p-4 bg-white flex items-center justify-between">
            <div>
              <span className="font-medium">{t.name}</span>
              <span className="ml-3 text-sm text-muted-foreground">{memberCounts[t.id] ?? 0} 位成員</span>
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => { setEditingTeam(t); setEditName(t.name) }}>
                ✏️
              </Button>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-500 hover:text-red-700" onClick={() => handleDelete(t)}>
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        ))}
        {teams.length === 0 && (
          <div className="text-center py-8 text-muted-foreground text-sm border rounded-lg bg-white">
            尚無部門，點擊「新增部門」開始建立
          </div>
        )}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>新增部門</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>部門名稱 *</Label>
              <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="例如：行銷業務一部" className="mt-1" />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={saving || !newName.trim()}>
                {saving ? '建立中...' : '建立'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editingTeam} onOpenChange={() => setEditingTeam(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>編輯部門</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>部門名稱</Label>
              <Input value={editName} onChange={e => setEditName(e.target.value)} className="mt-1" />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setEditingTeam(null)}>取消</Button>
              <Button onClick={handleUpdate} disabled={saving || !editName.trim()}>
                {saving ? '儲存中...' : '儲存'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Gmail Binding Card ────────────────────────────────────────────────────────
function GmailBindingCard() {
  const [connected, setConnected] = useState(false)
  const [gmailEmail, setGmailEmail] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [disconnecting, setDisconnecting] = useState(false)

  const loadStatus = async () => {
    try {
      const res = await getGmailStatus()
      setConnected(res.data.connected)
      setGmailEmail(res.data.email)
    } catch {
      setConnected(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'gmail-connected') {
        setConnected(true)
        setGmailEmail(e.data.email || null)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [])

  const handleConnect = async () => {
    try {
      const res = await getGmailAuthUrl()
      window.open(res.data.auth_url, '_blank', 'width=520,height=620,noopener')
    } catch {
      alert('無法取得授權連結，請確認 Google OAuth 設定')
    }
  }

  const handleDisconnect = async () => {
    if (!confirm('確定要解除 Gmail 綁定嗎？')) return
    setDisconnecting(true)
    try {
      await disconnectGmail()
      setConnected(false)
      setGmailEmail(null)
    } finally {
      setDisconnecting(false)
    }
  }

  return (
    <div className="bg-white border rounded-lg p-5 max-w-md">
      <div className="flex items-center gap-2 mb-4">
        <Mail className="w-4 h-4 text-gray-500" />
        <h3 className="text-sm font-medium text-gray-700">Gmail 發信帳號</h3>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">載入中...</p>
      ) : connected ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 px-3 py-2 rounded-lg">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <div>
              <p className="font-medium">已綁定</p>
              {gmailEmail && <p className="text-xs text-emerald-600 mt-0.5">{gmailEmail}</p>}
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleConnect}>重新授權</Button>
            <Button variant="outline" size="sm" onClick={handleDisconnect} disabled={disconnecting}
              className="text-red-500 hover:text-red-600 hover:bg-red-50 border-red-200">
              {disconnecting ? '解除中...' : '解除綁定'}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-gray-500 bg-gray-50 px-3 py-2 rounded-lg">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>尚未綁定 Gmail</span>
          </div>
          <p className="text-xs text-muted-foreground">
            綁定後即可直接從系統發送開發信，並追蹤回覆狀態。
          </p>
          <Button size="sm" onClick={handleConnect}>
            <Mail className="w-3.5 h-3.5 mr-1.5" /> 綁定 Gmail
          </Button>
        </div>
      )}
    </div>
  )
}

// ── Profile Tab ───────────────────────────────────────────────────────────────
function ProfileTab() {
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const handleChangePw = async () => {
    if (newPw !== confirmPw) {
      setMsg('❌ 新密碼與確認密碼不符')
      return
    }
    if (newPw.length < 8) {
      setMsg('❌ 密碼至少需要 8 個字元')
      return
    }
    if (!/[a-zA-Z]/.test(newPw)) {
      setMsg('❌ 密碼必須包含至少一個英文字母')
      return
    }
    if (!/[0-9]/.test(newPw)) {
      setMsg('❌ 密碼必須包含至少一個數字')
      return
    }
    setSaving(true)
    try {
      await changePassword(currentPw, newPw)
      setMsg('✅ 密碼已更新')
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setMsg(`❌ ${err?.response?.data?.detail || '更新失敗'}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-4">個人資料</h2>
        <div className="space-y-4">
          <GmailBindingCard />
        </div>
      </div>
      <div>
      <div className="bg-white border rounded-lg p-5 space-y-4 max-w-md">
        <h3 className="text-sm font-medium text-gray-700">更改密碼</h3>
        <div>
          <Label>目前密碼</Label>
          <PasswordInput value={currentPw} onChange={e => setCurrentPw(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label>新密碼</Label>
          <PasswordInput value={newPw} onChange={e => setNewPw(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label>確認新密碼</Label>
          <PasswordInput value={confirmPw} onChange={e => setConfirmPw(e.target.value)} className="mt-1" />
        </div>
        {msg && <p className="text-sm">{msg}</p>}
        <Button onClick={handleChangePw} disabled={saving || !currentPw || !newPw || !confirmPw}>
          {saving ? '更新中...' : '更改密碼'}
        </Button>
      </div>
      </div>
    </div>
  )
}
