import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { previewScraperJob, importScraperJob, findCompanyWebsite, findCompanyPhone, updateScraperJobField, ragicBulkCheck, ImportConflict, developScrapedLead, getScraperDevelopStatus } from '@/lib/api'
import ConflictReviewDialog from '@/components/ConflictReviewDialog'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Download, Building2, UserCircle2, Mail, Phone, MapPin, Briefcase, Search, Loader2, Database, Globe } from 'lucide-react'

// 與後端一致的公司名正規化（比對開發中狀態）
const _SUFFIXES = ['股份有限公司','有限公司','股份公司','企業社','工作室','公司','co.,ltd.','co., ltd.','co.ltd','co ltd','ltd.','ltd','inc.','inc','corporation','corp.','corp','company','co.','group','集團']
function normCompany(name: string): string {
  let n = (name || '').trim().toLowerCase()
  for (const s of _SUFFIXES) n = n.split(s).join('')
  n = n.replace(/台灣|臺灣|分公司|总公司|總公司/g, '')
  n = n.replace(/[\s\-_、,.()（）&·.]/g, '')
  return n
}

interface ScrapedCompany {
  company_name: string
  contact_name?: string
  email?: string
  phone?: string
  title?: string
  city?: string
  industry?: string
  website?: string
  // Threads 貼文模式專屬欄位
  post_text?: string
  likes?: number
  reposts?: number
  replies?: number
}

export default function ScraperJobPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [companies, setCompanies] = useState<ScrapedCompany[]>([])
  const [importing, setImporting] = useState(false)
  const [conflicts, setConflicts] = useState<ImportConflict[]>([])
  const [conflictNewCount, setConflictNewCount] = useState(0)
  const [showConflict, setShowConflict] = useState(false)
  const [error, setError] = useState('')
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set())
  const [findingWebsite, setFindingWebsite] = useState<Set<number>>(new Set())
  const [findingPhone, setFindingPhone] = useState<Set<number>>(new Set())
  const [bulkFinding, setBulkFinding] = useState(false)
  const [bulkProgress, setBulkProgress] = useState({ done: 0, total: 0 })
  // Ragic 重複檢查：company_name -> 'existing' | 'new' | 'none'
  const [ragicStatus, setRagicStatus] = useState<Map<string, 'existing' | 'new'>>(new Map())
  const [ragicChecking, setRagicChecking] = useState(false)
  // 開發中狀態：company_norm -> { developer_name, mine }
  const [devMap, setDevMap] = useState<Map<string, { developer_name: string; mine: boolean }>>(new Map())
  const [claiming, setClaiming] = useState<Set<number>>(new Set())

  const loadDevStatus = async (list: ScrapedCompany[]) => {
    const names = list.map(c => c.company_name).filter(Boolean)
    if (names.length === 0) return
    try {
      const res = await getScraperDevelopStatus(names)
      const m = new Map<string, { developer_name: string; mine: boolean }>()
      for (const [k, v] of Object.entries(res.data || {})) m.set(k, v)
      setDevMap(m)
    } catch { /* ignore */ }
  }

  // 業務勾選 → 認領為開發中
  const handleToggleDevelop = async (idx: number) => {
    const c = companies[idx]
    if (!c?.company_name) return
    const norm = normCompany(c.company_name)
    const cur = devMap.get(norm)
    if (cur && !cur.mine) { alert(`「${c.company_name}」該名單正在被開發中（業務：${cur.developer_name}）`); return }
    if (cur && cur.mine) return   // 已是自己的開發中
    if (claiming.has(idx)) return
    setClaiming(prev => new Set(prev).add(idx))
    try {
      const res = await developScrapedLead(c as unknown as Record<string, unknown>, id)
      if (res.data.locked) {
        alert(`「${c.company_name}」該名單正在被開發中（業務：${res.data.developer_name}）`)
        await loadDevStatus(companies)
        return
      }
      setDevMap(prev => new Map(prev).set(norm, { developer_name: res.data.developer_name || '我', mine: true }))
      // 一天提醒一次
      const key = 'dev_reminder_' + new Date().toISOString().slice(0, 10)
      if (!localStorage.getItem(key)) {
        alert('請於 24 小時後更新客戶資料，如未更新該客戶將開放所有業務認領')
        localStorage.setItem(key, '1')
      }
    } catch (e: any) {
      alert(e?.response?.data?.detail || '認領失敗，請稍後再試')
    } finally {
      setClaiming(prev => { const s = new Set(prev); s.delete(idx); return s })
    }
  }

  const handleBulkFindWebsite = async () => {
    const pending = companies.map((c, i) => ({ c, i })).filter(({ c }) => !c.website)
    if (pending.length === 0) return
    setBulkFinding(true)
    setBulkProgress({ done: 0, total: pending.length })
    for (const { c, i } of pending) {
      setFindingWebsite(prev => new Set(prev).add(i))
      try {
        const res = await findCompanyWebsite(c.company_name, c.city)
        const website: string | null = res.data.website
        if (website) {
          setCompanies(prev => prev.map((x, xi) => xi === i ? { ...x, website } : x))
          if (id) await updateScraperJobField(id, i, 'website', website)
        }
      } catch { /* 單筆失敗繼續 */ }
      setFindingWebsite(prev => { const s = new Set(prev); s.delete(i); return s })
      setBulkProgress(p => ({ ...p, done: p.done + 1 }))
    }
    setBulkFinding(false)
  }

  const performRagicCheck = async (targetCompanies: typeof companies) => {
    if (targetCompanies.length === 0) return
    setRagicChecking(true)
    try {
      const names = targetCompanies.map(c => c.company_name).filter(Boolean)
      const res = await ragicBulkCheck(names)
      const next = new Map<string, 'existing' | 'new'>()
      for (const r of res.data.results) {
        if (r.in_existing) next.set(r.company_name, 'existing')
        else if (r.in_new) next.set(r.company_name, 'new')
      }
      setRagicStatus(next)
    } catch (e: unknown) {
      console.error('自動 Ragic 檢查失敗', e)
    } finally {
      setRagicChecking(false)
    }
  }

  const handleRagicCheck = () => performRagicCheck(companies)

  useEffect(() => {
    if (!id) return
    const fetchJob = async () => {
      try {
        const res = await previewScraperJob(id)
        const comps = res.data.companies || []
        setCompanies(comps)
        loadDevStatus(comps)
        if (comps.length > 0) {
          performRagicCheck(comps)
        }
      } catch (err: any) {
        setError(err?.response?.data?.detail || '無法取得任務資料，或任務尚未完成')
      } finally {
        setLoading(false)
      }
    }
    fetchJob()
  }, [id])

  const allSelected = companies.length > 0 && selectedIndices.size === companies.length
  const someSelected = selectedIndices.size > 0

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIndices(new Set())
    } else {
      setSelectedIndices(new Set(companies.map((_, i) => i)))
    }
  }

  const toggleOne = (idx: number) => {
    setSelectedIndices(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const importCount = someSelected ? selectedIndices.size : companies.length

  const handleFindWebsite = async (idx: number, companyName: string) => {
    setFindingWebsite(prev => new Set(prev).add(idx))
    try {
      const res = await findCompanyWebsite(companyName, companies[idx]?.city)
      const url: string | null = res.data.website
      if (url) {
        setCompanies(prev => prev.map((c, i) => i === idx ? { ...c, website: url } : c))
        if (id) await updateScraperJobField(id, idx, 'website', url)
      } else {
        alert(`找不到「${companyName}」的官網`)
      }
    } catch {
      alert('搜尋失敗，請稍後再試')
    } finally {
      setFindingWebsite(prev => { const s = new Set(prev); s.delete(idx); return s })
    }
  }

  const handleFindPhone = async (idx: number, companyName: string) => {
    setFindingPhone(prev => new Set(prev).add(idx))
    try {
      const res = await findCompanyPhone(companyName, companies[idx]?.website, companies[idx]?.city)
      const phone: string | null = res.data.phone
      if (phone) {
        setCompanies(prev => prev.map((c, i) => i === idx ? { ...c, phone } : c))
        if (id) await updateScraperJobField(id, idx, 'phone', phone)
      } else {
        alert(`找不到「${companyName}」的電話`)
      }
    } catch {
      alert('搜尋失敗，請稍後再試')
    } finally {
      setFindingPhone(prev => { const s = new Set(prev); s.delete(idx); return s })
    }
  }

  const handleBulkFindPhone = async () => {
    const pending = companies.map((c, i) => ({ c, i })).filter(({ c }) => !c.phone)
    if (pending.length === 0) return
    setBulkFinding(true)
    setBulkProgress({ done: 0, total: pending.length })
    for (const { c, i } of pending) {
      setFindingPhone(prev => new Set(prev).add(i))
      try {
        const res = await findCompanyPhone(c.company_name, c.website, c.city)
        const phone: string | null = res.data.phone
        if (phone) {
          setCompanies(prev => prev.map((x, xi) => xi === i ? { ...x, phone } : x))
          if (id) await updateScraperJobField(id, i, 'phone', phone)
        }
      } catch { /* 單筆失敗繼續下一筆 */ }
      setFindingPhone(prev => { const s = new Set(prev); s.delete(i); return s })
      setBulkProgress(p => ({ ...p, done: p.done + 1 }))
    }
    setBulkFinding(false)
  }

  const importIndices = () => (someSelected ? Array.from(selectedIndices) : undefined)

  const handleImport = async () => {
    if (!id) return
    setImporting(true)
    try {
      const res = await importScraperJob(id, undefined, undefined, importIndices())
      if (res.data?.needs_review) {
        setConflicts(res.data.conflicts || [])
        setConflictNewCount(res.data.new_count || 0)
        setShowConflict(true)
        return
      }
      alert(`✅ 匯入完成：新增/更新 ${res.data.created} 筆，跳過 ${res.data.skipped} 筆`)
      navigate('/leads')
    } catch (err: any) {
      alert(err?.response?.data?.detail || '匯入失敗')
    } finally {
      setImporting(false)
    }
  }

  const handleConfirmConflicts = async (actions: Record<string, 'approve' | 'skip'>) => {
    if (!id) return
    setImporting(true)
    try {
      const res = await importScraperJob(id, undefined, undefined, importIndices(), {
        confirmed: true,
        conflict_actions: actions,
      })
      setShowConflict(false)
      const pending = res.data.pending_approval || 0
      alert(`✅ 匯入完成：新增/更新 ${res.data.created} 筆，跳過 ${res.data.skipped} 筆${pending ? `，送審核 ${pending} 筆` : ''}`)
      navigate('/leads')
    } catch (err: any) {
      alert(err?.response?.data?.detail || '匯入失敗')
    } finally {
      setImporting(false)
    }
  }

  if (loading) return <div className="flex p-8 items-center justify-center text-muted-foreground">載入中...</div>
  if (error) return <div className="p-8 text-destructive">{error}</div>

  const isPostsMode = companies.length > 0 && companies[0].post_text !== undefined
  const withEmailCount = companies.filter(c => c.email).length
  const withPhoneCount = companies.filter(c => c.phone).length

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/leads?tab=名單爬取')}>
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">爬蟲名單檢視</h1>
            <p className="text-sm text-muted-foreground">
              總共 {companies.length} 筆　有電話 {withPhoneCount} 筆　有 Email {withEmailCount} 筆
              <span className="ml-2 text-purple-600 font-medium">我的開發中 {Array.from(devMap.values()).filter(v => v.mine).length} 筆</span>
              <span className="ml-1 text-xs text-muted-foreground">（勾選名單＝認領為開發中）</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!isPostsMode && (
            <>
              <Button
                variant="outline"
                onClick={handleRagicCheck}
                disabled={ragicChecking || companies.length === 0}
                className="shadow-sm"
                title="批次查詢 Ragic 既有客戶 / 陌開表"
              >
                {ragicChecking
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Ragic 檢查中</>
                  : <><Database className="w-4 h-4 mr-2" />檢查 Ragic 重複{ragicStatus.size > 0 ? ` (${ragicStatus.size})` : ''}</>
                }
              </Button>
              <Button
                variant="outline"
                onClick={handleBulkFindPhone}
                disabled={bulkFinding || companies.filter(c => !c.phone).length === 0}
                className="shadow-sm"
              >
                {bulkFinding
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />查找中 {bulkProgress.done}/{bulkProgress.total}</>
                  : <><Search className="w-4 h-4 mr-2" />批量查找電話 ({companies.filter(c => !c.phone).length})</>
                }
              </Button>
              <Button
                variant="outline"
                onClick={handleBulkFindWebsite}
                disabled={bulkFinding || companies.filter(c => !c.website).length === 0}
                className="shadow-sm"
              >
                {bulkFinding
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />查找中 {bulkProgress.done}/{bulkProgress.total}</>
                  : <><Globe className="w-4 h-4 mr-2" />一鍵查詢網址 ({companies.filter(c => !c.website).length})</>
                }
              </Button>
            </>
          )}
        </div>
      </header>

      {/* List */}
      <main className="flex-1 overflow-auto p-6">
        <div className="bg-white border rounded-xl shadow-sm overflow-hidden text-sm">
          <table className="w-full text-left">
            <thead className="bg-gray-50 text-gray-600 font-medium">
              <tr>
                <th className="py-3 px-4 w-12 text-center text-gray-400 text-xs">開發</th>
                <th className="py-3 px-4 text-center text-gray-400 w-10">#</th>
                {isPostsMode ? (
                  <>
                    <th className="py-3 px-4">作者</th>
                    <th className="py-3 px-4">貼文內容</th>
                    <th className="py-3 px-4 w-24 text-center">👍 讚數</th>
                    <th className="py-3 px-4 w-24 text-center">🔁 轉發</th>
                    <th className="py-3 px-4 w-24 text-center">💬 留言</th>
                    <th className="py-3 px-4 hidden sm:table-cell w-36">貼文連結</th>
                  </>
                ) : (
                  <>
                    <th className="py-3 px-4">公司資訊</th>
                    <th className="py-3 px-4 hidden lg:table-cell w-40">電話</th>
                    <th className="py-3 px-4">聯絡人</th>
                    <th className="py-3 px-4 hidden sm:table-cell w-48">網址</th>
                    <th className="py-3 px-4 hidden lg:table-cell w-48">Email</th>
                    <th className="py-3 px-4 hidden md:table-cell w-36">產業/地理</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {companies.map((c, idx) => {
                const norm = normCompany(c.company_name)
                const dev = devMap.get(norm)
                const mine = !!dev?.mine
                const lockedByOther = !!dev && !dev.mine
                const checked = mine
                return (
                  <tr
                    key={idx}
                    onClick={() => handleToggleDevelop(idx)}
                    className={`transition-colors cursor-pointer ${mine ? 'bg-purple-50 hover:bg-purple-100' : lockedByOther ? 'bg-gray-50 opacity-70' : 'hover:bg-gray-50'}`}
                  >
                    <td className="py-4 px-4" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={lockedByOther || claiming.has(idx)}
                        onChange={() => handleToggleDevelop(idx)}
                        className="rounded text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                        title={lockedByOther ? `開發中（${dev?.developer_name}）` : '勾選＝認領為開發中'}
                      />
                    </td>

                    <td className="py-4 px-4 text-center text-xs text-gray-400">{idx + 1}</td>

                    {isPostsMode ? (
                      <>
                        {/* 作者欄 */}
                        <td className="py-2 px-4 w-36">
                          <div className="flex items-start gap-1.5">
                            <UserCircle2 className="w-4 h-4 text-indigo-500 mt-0.5 shrink-0" />
                            <div>
                              <div className="font-semibold text-gray-900 leading-tight text-sm">{c.company_name}</div>
                              <div className="text-xs text-gray-500">{c.contact_name}</div>
                            </div>
                          </div>
                        </td>
                        {/* 貼文內容 */}
                        <td className="py-2 px-4 max-w-xs">
                          <p className="text-xs text-gray-700 line-clamp-3 leading-relaxed whitespace-pre-wrap">
                            {c.post_text || <span className="text-gray-300 italic">（無內容）</span>}
                          </p>
                        </td>
                        {/* 讚數 */}
                        <td className="py-2 px-4 text-center">
                          <span className="text-sm font-medium text-rose-600">{c.likes ?? 0}</span>
                        </td>
                        {/* 轉發數 */}
                        <td className="py-2 px-4 text-center">
                          <span className="text-sm font-medium text-green-600">{c.reposts ?? 0}</span>
                        </td>
                        {/* 留言數 */}
                        <td className="py-2 px-4 text-center">
                          <span className="text-sm font-medium text-blue-600">{c.replies ?? 0}</span>
                        </td>
                        {/* 貼文連結 */}
                        <td className="py-2 px-4 hidden sm:table-cell" onClick={e => e.stopPropagation()}>
                          {c.website ? (
                            <a
                              href={c.website}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-indigo-500 hover:underline"
                            >
                              查看貼文 ↗
                            </a>
                          ) : <span className="text-xs text-gray-300">—</span>}
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2 px-4">
                          <div className="flex items-start gap-2">
                            <Building2 className="w-4 h-4 text-indigo-500 mt-0.5 shrink-0" />
                            <div>
                              <div className="font-semibold text-gray-900 leading-tight flex items-center gap-1.5 flex-wrap">
                                {c.company_name}
                                {ragicStatus.get(c.company_name) === 'existing' && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-normal" title="已在 Ragic 既有客戶表">既有客戶</span>
                                )}
                                {ragicStatus.get(c.company_name) === 'new' && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-normal" title="已在 Ragic 陌開表">陌開中</span>
                                )}
                                {dev && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-normal ${mine ? 'bg-purple-100 text-purple-700' : 'bg-gray-200 text-gray-600'}`} title="開發中">
                                    開發中{mine ? '（我）' : `（${dev.developer_name}）`}
                                  </span>
                                )}
                              </div>
                              {c.industry && <span className="text-xs text-muted-foreground mt-0.5 block md:hidden">{c.industry}</span>}
                            </div>
                          </div>
                        </td>

                        <td className="py-2 px-4 hidden lg:table-cell" onClick={e => e.stopPropagation()}>
                          {c.phone ? (
                            <div className="flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded w-fit group">
                              <Phone className="w-3.5 h-3.5 shrink-0" /> {c.phone}
                              <button
                                onClick={async () => {
                                  setCompanies(prev => prev.map((x, i) => i === idx ? { ...x, phone: undefined } : x))
                                  if (id) await updateScraperJobField(id, idx, 'phone', null)
                                }}
                                className="ml-1 opacity-0 group-hover:opacity-100 text-emerald-400 hover:text-red-500 transition-opacity"
                                title="清除電話"
                              >×</button>
                            </div>
                          ) : findingPhone.has(idx) ? (
                            <span className="flex items-center gap-1 text-xs text-gray-400">
                              <Loader2 className="w-3 h-3 animate-spin" /> 搜尋中...
                            </span>
                          ) : (
                            <button
                              onClick={() => handleFindPhone(idx, c.company_name)}
                              className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 px-2 py-1 rounded transition-colors"
                              title="自動搜尋電話並帶入"
                            >
                              <Search className="w-3 h-3" /> 查找電話
                            </button>
                          )}
                        </td>

                        <td className="py-2 px-4">
                          {c.contact_name ? (
                            <div className="flex items-start gap-2">
                              <UserCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
                              <div>
                                <p className="font-medium text-gray-800">{c.contact_name}</p>
                                {c.title && <p className="text-xs text-gray-500">{c.title}</p>}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-400 italic">— 無 —</span>
                          )}
                        </td>

                        <td className="py-2 px-4 hidden sm:table-cell" onClick={e => e.stopPropagation()}>
                          {c.website ? (
                            <a
                              href={c.website.startsWith('http') ? c.website : `https://${c.website}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-500 hover:underline text-xs break-all"
                            >
                              {c.website.length > 30 ? c.website.slice(0, 30) + '...' : c.website}
                            </a>
                          ) : findingWebsite.has(idx) ? (
                            <span className="flex items-center gap-1 text-xs text-gray-400">
                              <Loader2 className="w-3 h-3 animate-spin" /> 搜尋中...
                            </span>
                          ) : (
                            <button
                              onClick={() => handleFindWebsite(idx, c.company_name)}
                              className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 px-2 py-1 rounded transition-colors"
                              title="用 Google 搜尋官網"
                            >
                              <Search className="w-3 h-3" /> 查找網址
                            </button>
                          )}
                        </td>

                        <td className="py-2 px-4 hidden lg:table-cell">
                          {c.email ? (
                            <div className="flex items-center gap-1.5 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded w-fit max-w-[200px] truncate">
                              <Mail className="w-3.5 h-3.5 shrink-0" /> {c.email}
                            </div>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>

                        <td className="py-2 px-4 hidden md:table-cell">
                          <div className="space-y-1">
                            {c.industry && (
                              <div className="flex items-center gap-1.5 text-xs text-gray-600">
                                <Briefcase className="w-3.5 h-3.5" /> {c.industry}
                              </div>
                            )}
                            {c.city && (
                              <div className="flex items-center gap-1.5 text-xs text-gray-600">
                                <MapPin className="w-3.5 h-3.5" /> {c.city}
                              </div>
                            )}
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                )
              })}
              {companies.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-muted-foreground">
                    沒有資料
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>

      <ConflictReviewDialog
        open={showConflict}
        conflicts={conflicts}
        newCount={conflictNewCount}
        loading={importing}
        onCancel={() => setShowConflict(false)}
        onConfirm={handleConfirmConflicts}
      />
    </div>
  )
}
