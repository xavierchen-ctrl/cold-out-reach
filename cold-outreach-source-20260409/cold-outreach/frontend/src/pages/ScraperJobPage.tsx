import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { previewScraperJob, importScraperJob, findCompanyWebsite, updateScraperJobField } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Download, Building2, UserCircle2, Mail, Phone, MapPin, Briefcase, Search, Loader2, X } from 'lucide-react'

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
  const [error, setError] = useState('')
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set())
  const [findingWebsite, setFindingWebsite] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!id) return
    const fetchJob = async () => {
      try {
        const res = await previewScraperJob(id)
        setCompanies(res.data.companies || [])
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
      const res = await findCompanyWebsite(companyName)
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

  const handleImport = async () => {
    if (!id) return
    setImporting(true)
    try {
      const indices = someSelected ? Array.from(selectedIndices) : undefined
      const res = await importScraperJob(id, undefined, undefined, indices)
      alert(`✅ 匯入完成：新增/更新 ${res.data.created} 筆，跳過 ${res.data.skipped} 筆`)
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
          <Button variant="ghost" size="icon" onClick={() => navigate('/leads?tab=會展爬取')}>
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">爬蟲名單檢視</h1>
            <p className="text-sm text-muted-foreground">
              總共 {companies.length} 筆　有電話 {withPhoneCount} 筆　有 Email {withEmailCount} 筆
              {someSelected && <span className="ml-2 text-primary font-medium">已勾選 {selectedIndices.size} 筆</span>}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <Button onClick={handleImport} disabled={importing} className="shadow-sm">
            <Download className="w-4 h-4 mr-2" />
            {importing ? '匯入中...' : `匯入名單 (${importCount})`}
          </Button>
        </div>
      </header>

      {/* List */}
      <main className="flex-1 overflow-auto p-6">
        <div className="bg-white border rounded-xl shadow-sm overflow-hidden text-sm">
          <table className="w-full text-left">
            <thead className="bg-gray-50 text-gray-600 font-medium">
              <tr>
                <th className="py-3 px-4 w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
                    onChange={toggleAll}
                    className="rounded text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                    title={allSelected ? '取消全選' : '全選'}
                  />
                </th>
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
                    <th className="py-3 px-4 hidden sm:table-cell w-48">網址</th>
                    <th className="py-3 px-4">聯絡人</th>
                    <th className="py-3 px-4 hidden md:table-cell w-36">地理/產業</th>
                    <th className="py-3 px-4 hidden lg:table-cell w-40">電話</th>
                    <th className="py-3 px-4 hidden lg:table-cell w-48">Email</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {companies.map((c, idx) => {
                const checked = selectedIndices.has(idx)
                return (
                  <tr
                    key={idx}
                    onClick={() => toggleOne(idx)}
                    className={`transition-colors cursor-pointer ${checked ? 'bg-blue-50 hover:bg-blue-100' : 'hover:bg-gray-50'}`}
                  >
                    <td className="py-4 px-4" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleOne(idx)}
                        className="rounded text-primary focus:ring-primary w-4 h-4 cursor-pointer"
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
                              <div className="font-semibold text-gray-900 leading-tight">{c.company_name}</div>
                              {c.industry && <span className="text-xs text-muted-foreground mt-0.5 block md:hidden">{c.industry}</span>}
                            </div>
                          </div>
                        </td>

                        <td className="py-2 px-4 hidden sm:table-cell" onClick={e => e.stopPropagation()}>
                          {c.website ? (
                            <div className="flex items-center gap-1 group">
                              <a
                                href={c.website.startsWith('http') ? c.website : `https://${c.website}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-500 hover:underline text-xs break-all"
                              >
                                {c.website.length > 30 ? c.website.slice(0, 30) + '...' : c.website}
                              </a>
                              <button
                                title="清除網址，重新查找"
                                className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity flex-shrink-0"
                                onClick={async () => {
                                  setCompanies(prev => prev.map((item, i) => i === idx ? { ...item, website: undefined } : item))
                                  if (id) await updateScraperJobField(id, idx, 'website', null)
                                }}
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </div>
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

                        <td className="py-2 px-4 hidden lg:table-cell">
                          {c.phone ? (
                            <div className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded w-fit">
                              <Phone className="w-3.5 h-3.5 shrink-0" /> {c.phone}
                            </div>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
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
    </div>
  )
}
