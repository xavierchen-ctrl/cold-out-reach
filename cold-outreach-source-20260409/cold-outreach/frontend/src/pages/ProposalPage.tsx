import { useState } from 'react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { FileDown, Loader2, Presentation } from 'lucide-react'

const SERVICES = ['廣告投放', 'SEO優化', '社群代操', 'KOL行銷', 'LINE CRM', 'YouTube 影音', '整合行銷']
const BUDGETS = ['50萬以下', '50', '100', '150', '200', '300', '500']

export default function ProposalPage() {
  const [form, setForm] = useState({
    client_name: '',
    industry: '',
    current_situation: '',
    monthly_budget: '100',
    special_notes: '',
    year: 2026,
  })
  const [services, setServices] = useState<string[]>(['廣告投放', 'SEO優化'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const toggleService = (s: string) =>
    setServices(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.client_name || !form.industry || !form.current_situation) {
      setError('請填寫客戶名稱、產業、品牌現況')
      return
    }
    if (services.length === 0) {
      setError('請至少選擇一項主推服務')
      return
    }
    setError('')
    setLoading(true)
    setDone(false)
    try {
      const res = await api.post(
        '/proposal/generate',
        { ...form, services },
        { responseType: 'blob' }
      )
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `${form.client_name}_${form.year}_媒體提案.pptx`
      a.click()
      URL.revokeObjectURL(url)
      setDone(true)
    } catch (err: unknown) {
      const text = await (err as { response?: { data?: Blob } })?.response?.data?.text?.()
      try {
        const json = JSON.parse(text || '{}')
        setError(json.detail || '生成失敗，請稍後再試')
      } catch {
        setError('生成失敗，請稍後再試')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <Presentation className="w-7 h-7 text-primary" />
        <div>
          <h1 className="text-xl font-bold">媒體提案生成</h1>
          <p className="text-sm text-muted-foreground">填寫客戶資訊，AI 自動生成 16 頁 PPTX 提案檔</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Basic info */}
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">客戶基本資訊</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>客戶名稱 *</Label>
              <Input
                placeholder="例：Healthing"
                value={form.client_name}
                onChange={e => setForm(f => ({ ...f, client_name: e.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label>產業 *</Label>
              <Input
                placeholder="例：保健食品、電商、教育"
                value={form.industry}
                onChange={e => setForm(f => ({ ...f, industry: e.target.value }))}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>品牌現況說明 *</Label>
            <Textarea
              rows={4}
              placeholder="說明客戶目前的品牌狀況、主要商品、遇到的問題、目前行銷方式等（越詳細 AI 生成越精準）"
              value={form.current_situation}
              onChange={e => setForm(f => ({ ...f, current_situation: e.target.value }))}
            />
          </div>
        </div>

        {/* Services */}
        <div className="bg-white border rounded-xl p-5 space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">主推服務（可多選）</h2>
          <div className="flex flex-wrap gap-2">
            {SERVICES.map(s => (
              <button
                key={s}
                type="button"
                onClick={() => toggleService(s)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  services.includes(s)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Budget & Year */}
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">預算與年度</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>月預算（萬）</Label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm bg-white"
                value={form.monthly_budget}
                onChange={e => setForm(f => ({ ...f, monthly_budget: e.target.value }))}
              >
                {BUDGETS.map(b => (
                  <option key={b} value={b}>{b === '50萬以下' ? b : `${b} 萬`}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>提案年度</Label>
              <Input
                type="number"
                value={form.year}
                onChange={e => setForm(f => ({ ...f, year: Number(e.target.value) }))}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>特殊需求或備注（選填）</Label>
            <Input
              placeholder="例：重點強調 LINE CRM、不含 YouTube 策略..."
              value={form.special_notes}
              onChange={e => setForm(f => ({ ...f, special_notes: e.target.value }))}
            />
          </div>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {done && (
          <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
            <FileDown className="w-4 h-4" />
            PPTX 已下載！可在下載資料夾找到檔案。
          </div>
        )}

        <Button type="submit" className="w-full h-11 text-base gap-2" disabled={loading}>
          {loading ? (
            <><Loader2 className="w-4 h-4 animate-spin" />AI 生成中，約需 20-30 秒...</>
          ) : (
            <><FileDown className="w-4 h-4" />生成 PPTX 提案檔</>
          )}
        </Button>

        <p className="text-xs text-center text-muted-foreground">
          生成後自動下載 .pptx 檔，可用 PowerPoint 或 Google 簡報開啟後自由編輯
        </p>
      </form>
    </div>
  )
}
