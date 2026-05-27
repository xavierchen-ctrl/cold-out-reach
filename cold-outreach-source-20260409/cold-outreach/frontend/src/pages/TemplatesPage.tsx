import { useState, useEffect, useCallback } from 'react'
import { getTemplates, createTemplate, updateTemplate, deleteTemplate } from '@/lib/api'
import { EmailTemplate } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Pencil, Trash2, Mail } from 'lucide-react'

const TYPE_LABELS: Record<string, string> = {
  intro: '初次開發',
  followup: '跟進追蹤',
  proposal: '報價提案',
  custom: '自訂',
}

const TYPE_COLORS: Record<string, string> = {
  intro: 'bg-blue-100 text-blue-700',
  followup: 'bg-yellow-100 text-yellow-700',
  proposal: 'bg-green-100 text-green-700',
  custom: 'bg-gray-100 text-gray-700',
}

interface TemplateFormProps {
  initial?: Partial<EmailTemplate>
  onSave: (data: Partial<EmailTemplate>) => Promise<void>
  onClose: () => void
}

function TemplateForm({ initial, onSave, onClose }: TemplateFormProps) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    subject: initial?.subject || '',
    body: initial?.body || '',
    template_type: initial?.template_type || 'custom',
  })
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await onSave(form)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{initial?.id ? '編輯模板' : '新增模板'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>模板名稱 *</Label>
              <Input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                required
                className="mt-1"
              />
            </div>
            <div>
              <Label>類型</Label>
              <Select value={form.template_type} onValueChange={v => setForm(f => ({ ...f, template_type: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(TYPE_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>主旨 *</Label>
            <Input
              value={form.subject}
              onChange={e => setForm(f => ({ ...f, subject: e.target.value }))}
              required
              className="mt-1"
              placeholder="支援 {{company_name}} {{contact_name}} 等變數"
            />
          </div>
          <div>
            <Label>內文 *</Label>
            <Textarea
              value={form.body}
              onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
              required
              rows={12}
              className="mt-1 font-mono text-sm"
              placeholder="支援 {{company_name}} {{contact_name}} {{industry}} 等變數"
            />
          </div>
          <div className="text-xs text-muted-foreground bg-muted p-3 rounded">
            可用變數：<code>{'{{company_name}}'}</code>、<code>{'{{contact_name}}'}</code>、
            <code>{'{{industry}}'}</code>、<code>{'{{city}}'}</code>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>取消</Button>
            <Button type="submit" disabled={saving}>{saving ? '儲存中...' : '儲存'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<EmailTemplate | null | 'new'>(null)
  const [preview, setPreview] = useState<EmailTemplate | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getTemplates()
      setTemplates(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async (data: Partial<EmailTemplate>) => {
    if (editing && editing !== 'new' && editing.id) {
      await updateTemplate(editing.id, data)
    } else {
      await createTemplate(data)
    }
    await load()
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此模板？')) return
    await deleteTemplate(id)
    await load()
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">信件模板庫</h1>
          <p className="text-sm text-muted-foreground mt-0.5">管理你的發信模板</p>
        </div>
        <Button onClick={() => setEditing('new')}>
          <Plus className="w-4 h-4 mr-1.5" /> 新增模板
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">載入中...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map(tmpl => (
            <div key={tmpl.id} className="bg-white border rounded-xl p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-muted-foreground" />
                  <span className="font-medium text-sm">{tmpl.name}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[tmpl.template_type] || TYPE_COLORS.custom}`}>
                  {TYPE_LABELS[tmpl.template_type] || tmpl.template_type}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mb-2 truncate">{tmpl.subject}</p>
              <p className="text-xs text-gray-600 line-clamp-3 whitespace-pre-wrap">{tmpl.body}</p>
              <div className="flex gap-2 mt-4 pt-3 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => setPreview(tmpl)}
                >
                  預覽
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(tmpl)}
                >
                  <Pencil className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => handleDelete(tmpl.id)}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit/Create modal */}
      {editing && (
        <TemplateForm
          initial={editing === 'new' ? {} : editing}
          onSave={handleSave}
          onClose={() => setEditing(null)}
        />
      )}

      {/* Preview modal */}
      {preview && (
        <Dialog open onOpenChange={() => setPreview(null)}>
          <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{preview.name}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="p-3 bg-muted rounded">
                <p className="text-xs text-muted-foreground mb-1">主旨</p>
                <p className="text-sm font-medium">{preview.subject}</p>
              </div>
              <div className="p-3 bg-muted rounded">
                <p className="text-xs text-muted-foreground mb-1">內文</p>
                <pre className="text-sm whitespace-pre-wrap font-sans">{preview.body}</pre>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
