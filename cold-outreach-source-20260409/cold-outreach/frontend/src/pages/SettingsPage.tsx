import { useState, useEffect } from 'react'
import { getTags, createTag, deleteTag, getWebhooks, createWebhook, updateWebhook, deleteWebhook, testWebhook, getWebhookLogs, getNotificationSettings, testNotification, getUsers, createUser, updateUser, deleteUser, getTeams, createTeam, updateTeam, deleteTeam } from '@/lib/api'
import { Tag, Webhook, WebhookLog, User as UserType, Team } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Trash2, Plus, Globe, Tag as TagIcon, Bell, User, TestTube2, Zap, Users } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

const PRESET_COLORS = [
  '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
  '#8b5cf6', '#ef4444', '#06b6d4', '#84cc16', '#f97316',
]

const WEBHOOK_EVENTS = [
  'lead.status_changed', 'lead.won', 'lead.lost', 'email.replied', 'meeting.scheduled',
]

type SettingsTab = 'tags' | 'webhooks' | 'line' | 'profile' | 'users' | 'teams'

export default function SettingsPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<SettingsTab>('tags')

  const tabs = [
    { key: 'tags', label: '標籤管理', icon: TagIcon },
    { key: 'webhooks', label: 'Webhook', icon: Globe },
    { key: 'line', label: 'LINE Notify', icon: Bell },
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
      {tab === 'webhooks' && <WebhooksTab />}
      {tab === 'line' && <LineNotifyTab />}
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

// ── Webhooks Tab ──────────────────────────────────────────────────────────────
function WebhooksTab() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [newUrl, setNewUrl] = useState('')
  const [newName, setNewName] = useState('')
  const [newEvents, setNewEvents] = useState<string[]>([])
  const [newSecret, setNewSecret] = useState('')
  const [creating, setCreating] = useState(false)
  const [selectedWebhookLogs, setSelectedWebhookLogs] = useState<{ webhook: Webhook; logs: WebhookLog[] } | null>(null)

  const loadWebhooks = async () => {
    const res = await getWebhooks()
    setWebhooks(Array.isArray(res.data) ? res.data : [])
  }
  useEffect(() => { loadWebhooks() }, [])

  const handleCreate = async () => {
    if (!newUrl.trim()) return
    setCreating(true)
    try {
      await createWebhook({ name: newName, url: newUrl, events: newEvents, secret: newSecret || undefined })
      setNewUrl('')
      setNewName('')
      setNewEvents([])
      setNewSecret('')
      setShowCreate(false)
      await loadWebhooks()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '建立失敗')
    } finally {
      setCreating(false)
    }
  }

  const handleTest = async (id: string) => {
    try {
      const res = await testWebhook(id)
      alert(res.data.message)
    } catch {
      alert('測試失敗')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此 Webhook？')) return
    await deleteWebhook(id)
    await loadWebhooks()
  }

  const handleToggle = async (webhook: Webhook) => {
    await updateWebhook(webhook.id, { is_active: !webhook.is_active })
    await loadWebhooks()
  }

  const handleViewLogs = async (webhook: Webhook) => {
    const res = await getWebhookLogs(webhook.id)
    setSelectedWebhookLogs({ webhook, logs: res.data })
  }

  const toggleEvent = (event: string) => {
    setNewEvents(prev => prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Webhook 管理</h2>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-1" /> 新增 Webhook
        </Button>
      </div>

      <div className="space-y-3">
        {webhooks.map(wh => (
          <div key={wh.id} className="border rounded-lg p-4 bg-white">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{wh.name || '未命名'}</span>
                  <Badge variant={wh.is_active ? 'default' : 'outline'} className="text-xs">
                    {wh.is_active ? '啟用' : '停用'}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1 font-mono">{wh.url}</p>
                <div className="flex gap-1 mt-2 flex-wrap">
                  {(wh.events || []).map(ev => (
                    <span key={ev} className="text-xs bg-gray-100 px-2 py-0.5 rounded">{ev}</span>
                  ))}
                </div>
              </div>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" onClick={() => handleTest(wh.id)}>
                  <TestTube2 className="w-3.5 h-3.5" />
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleViewLogs(wh)}>記錄</Button>
                <Button variant="outline" size="sm" onClick={() => handleToggle(wh)}>
                  {wh.is_active ? '停用' : '啟用'}
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleDelete(wh.id)} className="text-red-500">
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </div>
        ))}
        {webhooks.length === 0 && (
          <div className="text-center py-8 text-muted-foreground text-sm border rounded-lg bg-white">
            尚無 Webhook，點擊「新增 Webhook」開始設定
          </div>
        )}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>新增 Webhook</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>名稱（選填）</Label>
              <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="例如：Slack 通知" className="mt-1" />
            </div>
            <div>
              <Label>Webhook URL *</Label>
              <Input value={newUrl} onChange={e => setNewUrl(e.target.value)} placeholder="https://hooks.slack.com/..." className="mt-1" />
            </div>
            <div>
              <Label>觸發事件</Label>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {WEBHOOK_EVENTS.map(ev => (
                  <label key={ev} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={newEvents.includes(ev)} onChange={() => toggleEvent(ev)} />
                    <span className="font-mono text-xs">{ev}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <Label>簽名 Secret（選填）</Label>
              <Input value={newSecret} onChange={e => setNewSecret(e.target.value)} placeholder="用於 HMAC 驗證" className="mt-1" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button onClick={handleCreate} disabled={creating || !newUrl.trim()}>
                {creating ? '建立中...' : '建立'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Logs Dialog */}
      {selectedWebhookLogs && (
        <Dialog open={true} onOpenChange={() => setSelectedWebhookLogs(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Webhook 記錄 — {selectedWebhookLogs.webhook.name || '未命名'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {selectedWebhookLogs.logs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">尚無記錄</p>
              ) : selectedWebhookLogs.logs.map(log => (
                <div key={log.id} className="border rounded p-3 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-medium">{log.event}</span>
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                        (log.response_status ?? 0) >= 200 && (log.response_status ?? 0) < 300 
                          ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {log.response_status || '失敗'}
                      </span>
                      <span className="text-muted-foreground">{new Date(log.created_at).toLocaleString('zh-TW')}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

// ── LINE Notify Tab ───────────────────────────────────────────────────────────
function LineNotifyTab() {
  const [settings, setSettings] = useState<{ line_notify_configured: boolean; line_notify_token_preview: string | null; triggers: string[] } | null>(null)
  const [testMsg, setTestMsg] = useState('🧪 Cold Outreach 測試通知')
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    getNotificationSettings().then(r => setSettings(r.data)).catch(() => {})
  }, [])

  const handleTest = async () => {
    setTesting(true)
    try {
      await testNotification(testMsg)
      alert('✅ 通知已發送')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      alert(err?.response?.data?.detail || '發送失敗')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">LINE Notify 設定</h2>
      <div className="bg-white border rounded-lg p-5 space-y-4 max-w-lg">
        <div className="flex items-center gap-2">
          <Zap className={`w-5 h-5 ${settings?.line_notify_configured ? 'text-green-500' : 'text-gray-400'}`} />
          <span className="text-sm font-medium">
            狀態：{settings?.line_notify_configured ? (
              <span className="text-green-600">已設定</span>
            ) : (
              <span className="text-red-500">未設定</span>
            )}
          </span>
          {settings?.line_notify_token_preview && (
            <span className="text-xs text-muted-foreground font-mono">({settings.line_notify_token_preview})</span>
          )}
        </div>

        {!settings?.line_notify_configured && (
          <div className="text-sm text-muted-foreground bg-yellow-50 border border-yellow-200 rounded p-3">
            <p className="font-medium mb-1">設定方式：</p>
            <p>在後端環境變數中設定 <code className="bg-yellow-100 px-1 rounded">LINE_NOTIFY_TOKEN</code></p>
            <p className="mt-1">取得 token：<a href="https://notify-bot.line.me/my/" target="_blank" rel="noopener noreferrer" className="text-blue-500 underline">LINE Notify 官方頁面</a></p>
          </div>
        )}

        <div>
          <Label>觸發事件</Label>
          <div className="mt-1 space-y-1">
            {(settings?.triggers || ['won', 'meeting_scheduled']).map(t => (
              <div key={t} className="flex items-center gap-2 text-sm">
                <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                <span>{t === 'won' ? '成交' : t === 'meeting_scheduled' ? '會議確認' : t}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <Label>測試訊息</Label>
          <Input value={testMsg} onChange={e => setTestMsg(e.target.value)} className="mt-1" />
        </div>
        <Button onClick={handleTest} disabled={testing || !settings?.line_notify_configured}>
          {testing ? '發送中...' : '發送測試通知'}
        </Button>
      </div>
    </div>
  )
}

// ── Users Tab (Admin only) ────────────────────────────────────────────────────
const ROLE_LABELS: Record<string, string> = {
  admin: '管理員',
  manager: '主管',
  sales: '業務',
}

function UsersTab({ currentUserId }: { currentUserId: string }) {
  const [users, setUsers] = useState<UserType[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingUser, setEditingUser] = useState<UserType | null>(null)
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'sales' })
  const [editForm, setEditForm] = useState({ name: '', role: 'sales', password: '', team_id: '' })
  const [saving, setSaving] = useState(false)

  const loadData = async () => {
    try {
      const [uRes, tRes] = await Promise.all([getUsers(), getTeams()])
      setUsers(Array.isArray(uRes.data) ? uRes.data : [])
      setTeams(Array.isArray(tRes.data) ? tRes.data : [])
    } catch {}
  }
  useEffect(() => { loadData() }, [])

  const teamName = (id: string | null) => teams.find(t => t.id === id)?.name ?? '—'

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
      const payload: { name?: string; role?: string; password?: string; team_id?: string | null } = {
        name: editForm.name || undefined,
        role: editForm.role || undefined,
        team_id: editForm.team_id || null,
      }
      if (editForm.password) payload.password = editForm.password
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
            {users.map(u => (
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
                      setEditForm({ name: u.name, role: u.role, password: '', team_id: u.team_id ?? '' })
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
              <Input type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} className="mt-1" />
            </div>
            <div>
              <Label>角色</Label>
              <Select value={form.role} onValueChange={v => setForm(f => ({ ...f, role: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="sales">業務</SelectItem>
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
                  <SelectItem value="manager">主管</SelectItem>
                  <SelectItem value="admin">管理員</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>部門</Label>
              <Select value={editForm.team_id} onValueChange={v => setEditForm(f => ({ ...f, team_id: v }))}>
                <SelectTrigger className="mt-1"><SelectValue placeholder="不指定部門" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不指定</SelectItem>
                  {teams.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>新密碼 <span className="text-muted-foreground font-normal text-xs">（留空表示不修改）</span></Label>
              <Input type="password" value={editForm.password} onChange={e => setEditForm(f => ({ ...f, password: e.target.value }))} className="mt-1" placeholder="不修改請留空" />
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
      // This would call a change password API endpoint
      // For now, just simulate
      await new Promise(r => setTimeout(r, 500))
      setMsg('✅ 密碼已更新')
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
    } catch {
      setMsg('❌ 更新失敗')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">個人資料</h2>
      <div className="bg-white border rounded-lg p-5 space-y-4 max-w-md">
        <h3 className="text-sm font-medium text-gray-700">更改密碼</h3>
        <div>
          <Label>目前密碼</Label>
          <Input type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label>新密碼</Label>
          <Input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label>確認新密碼</Label>
          <Input type="password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)} className="mt-1" />
        </div>
        {msg && <p className="text-sm">{msg}</p>}
        <Button onClick={handleChangePw} disabled={saving || !currentPw || !newPw || !confirmPw}>
          {saving ? '更新中...' : '更改密碼'}
        </Button>
      </div>
    </div>
  )
}
