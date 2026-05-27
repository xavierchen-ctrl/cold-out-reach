import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { previewScraperJob, importScraperJob } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Download, Building2, UserCircle2, Mail, Phone, MapPin, Briefcase } from 'lucide-react'

interface ScrapedCompany {
  company_name: string
  contact_name?: string
  email?: string
  phone?: string
  title?: string
  city?: string
  industry?: string
  website?: string
}

export default function ScraperJobPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  
  const [loading, setLoading] = useState(true)
  const [companies, setCompanies] = useState<ScrapedCompany[]>([])
  const [importEmailOnly, setImportEmailOnly] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')

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

  const handleImport = async () => {
    if (!id) return
    setImporting(true)
    try {
      const res = await importScraperJob(id, undefined, importEmailOnly)
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

  const displayedCount = companies.length
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
            <p className="text-sm text-muted-foreground">總共掃描到 {displayedCount} 間公司　有電話 {withPhoneCount} 筆　有 Email {withEmailCount} 筆</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none bg-gray-100 px-3 py-1.5 rounded-full text-gray-700">
            <input
              type="checkbox"
              checked={importEmailOnly}
              onChange={e => setImportEmailOnly(e.target.checked)}
              className="rounded text-primary focus:ring-primary w-4 h-4"
            />
            <span>只匯入有 Email 的 ({withEmailCount} 筆)</span>
          </label>
          <Button onClick={handleImport} disabled={importing} className="shadow-sm">
            <Download className="w-4 h-4 mr-2" />
            {importing ? '匯入中...' : `匯入名單 (${importEmailOnly ? withEmailCount : displayedCount})`}
          </Button>
        </div>
      </header>

      {/* List */}
      <main className="flex-1 overflow-auto p-6">
        <div className="bg-white border rounded-xl shadow-sm overflow-hidden text-sm">
          <table className="w-full text-left">
            <thead className="bg-gray-50 text-gray-600 font-medium">
              <tr>
                <th className="py-3 px-4 text-center text-gray-400 w-12">#</th>
                <th className="py-3 px-4">公司資訊</th>
                <th className="py-3 px-4 hidden sm:table-cell w-48">網址</th>
                <th className="py-3 px-4">聯絡人</th>
                <th className="py-3 px-4 hidden md:table-cell w-36">地理/產業</th>
                <th className="py-3 px-4 hidden lg:table-cell w-40">電話</th>
                <th className="py-3 px-4 hidden lg:table-cell w-48">Email</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {companies.map((c, idx) => (
                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                  <td className="py-4 px-4 text-center text-xs text-gray-400">{idx + 1}</td>
                  
                  <td className="py-2 px-4">
                    <div className="flex items-start gap-2">
                      <Building2 className="w-4 h-4 text-indigo-500 mt-0.5 shrink-0" />
                      <div>
                        <div className="font-semibold text-gray-900 leading-tight">{c.company_name}</div>
                        {c.industry && <span className="text-xs text-muted-foreground mt-0.5 block md:hidden">{c.industry}</span>}
                      </div>
                    </div>
                  </td>

                  <td className="py-2 px-4 hidden sm:table-cell">
                    {c.website ? (
                      <a href={c.website.startsWith('http') ? c.website : `https://${c.website}`} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline text-xs break-all">
                        {c.website.length > 30 ? c.website.slice(0, 30) + '...' : c.website}
                      </a>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
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

                </tr>
              ))}
              {companies.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-muted-foreground">
                    沒有公司資料
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
