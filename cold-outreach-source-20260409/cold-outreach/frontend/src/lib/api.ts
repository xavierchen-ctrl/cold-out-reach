import axios from 'axios'

// 本機開發：VITE_API_URL 未設定 → 用 Vite proxy（/api → localhost:8000）
// 生產（Vercel）：VITE_API_URL=https://xxx.railway.app → 直接打後端
const _base = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({
  baseURL: _base,
  withCredentials: true,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // /api/auth/me 的 401 讓 useAuth 自己處理，不強制跳轉
      const url = err.config?.url || ''
      if (!url.includes('/auth/me') && !url.includes('/auth/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (email: string, password: string) =>
  api.post('/auth/login', { email, password })
export const logout = () => api.post('/auth/logout')
export const getMe = () => api.get('/auth/me')
export const changePassword = (current_password: string, new_password: string) =>
  api.post('/auth/me/change-password', { current_password, new_password })

// ── Leads ─────────────────────────────────────────────────────────────────────
export const getLeads = (params?: Record<string, string | number>) =>
  api.get('/leads', { params })
export const getLead = (id: string) => api.get(`/leads/${id}`)
export const createLead = (data: Record<string, unknown>) => api.post('/leads', data)
export const updateLead = (id: string, data: Record<string, unknown>) =>
  api.patch(`/leads/${id}`, data)
export const deleteLead = (id: string) => api.delete(`/leads/${id}`)
export const updateLeadStatus = (id: string, status: string) =>
  api.patch(`/leads/${id}/status`, { status })
export const importCSV = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/leads/import', form)
}

// ── Activities ────────────────────────────────────────────────────────────────
export const getActivities = (leadId: string) =>
  api.get(`/leads/${leadId}/activities`)
export const createActivity = (leadId: string, data: Record<string, unknown>) =>
  api.post(`/leads/${leadId}/activities`, data)

// ── Gmail ─────────────────────────────────────────────────────────────────────
export const getGmailAuthUrl = () => api.get('/gmail/auth')
export const sendEmail = (data: Record<string, unknown>) => api.post('/gmail/send', data)

// ── AI ────────────────────────────────────────────────────────────────────────
export const generateDraft = (lead_id: string, template_type: string, customer_background?: string) =>
  api.post('/ai/draft', { lead_id, template_type, customer_background })

// ── Stats ─────────────────────────────────────────────────────────────────────
export const getStatsOverview = () => api.get('/stats/overview')
export const getStatsBySales = () => api.get('/stats/by_sales')
export const getStatsFunnel = () => api.get('/stats/funnel')
export const getStatsTrend = () => api.get('/stats/trend')
export const getStaleLeads = () => api.get('/stats/stale_leads')
export const getAiSuggestions = (refresh = false) => api.get('/stats/ai_suggestions', { params: { refresh } })

// ── Enrich ───────────────────────────────────────────────────────────────────
export const enrichLushaPhone = (lead_ids?: string[], limit = 20) =>
  api.post('/enrich/lusha/phone', { lead_ids, limit })
export const enrichLushaStatus = (job_id: string) =>
  api.get(`/enrich/lusha/phone/${job_id}`)

// ── Scoring ───────────────────────────────────────────────────────────────────
export const scoreLead = (id: string) => api.post(`/leads/${id}/score`)
export const scoreBatch = (lead_ids?: string[]) =>
  api.post('/leads/score/batch', lead_ids ? { lead_ids } : { all: true })

// ── Bulk ──────────────────────────────────────────────────────────────────────
export const bulkStatus = (lead_ids: string[], status: string) =>
  api.post('/leads/bulk/status', { lead_ids, status })
export const bulkAssign = (lead_ids: string[], user_id: string) =>
  api.post('/leads/bulk/assign', { lead_ids, user_id })
export const bulkDelete = (lead_ids: string[]) =>
  api.post('/leads/bulk/delete', { lead_ids })

// ── Sequences ─────────────────────────────────────────────────────────────────
export const getSequences = () => api.get('/sequences')
export const createSequence = (data: Record<string, unknown>) => api.post('/sequences', data)
export const deleteSequence = (id: string) => api.delete(`/sequences/${id}`)
export const enrollSequence = (seq_id: string, lead_ids: string[]) =>
  api.post(`/sequences/${seq_id}/enroll`, { lead_ids })
export const processSequences = () => api.post('/sequences/process')
export const getPendingEmails = () => api.get('/sequences/pending')
export const sendPendingEmail = (id: string) => api.post(`/sequences/pending/${id}/send`)
export const skipPendingEmail = (id: string) => api.post(`/sequences/pending/${id}/skip`)

// ── Scraper ───────────────────────────────────────────────────────────────────
export const runScraper = (source: string, url?: string, keyword?: string, industry?: string, limit?: number) =>
  api.post('/scraper/run', { source, url, keyword, industry, limit })
export const getScraperJobs = () => api.get('/scraper/jobs')
export const previewScraperJob = (jobId: string) =>
  api.get(`/scraper/preview/${jobId}`)
export const importScraperJob = (jobId: string, assigned_to?: string, email_only?: boolean, indices?: number[]) =>
  api.post(`/scraper/import/${jobId}`, { assigned_to, email_only, indices })
export const findCompanyWebsite = (q: string) =>
  api.get(`/scraper/find-website`, { params: { q } })
export const updateScraperJobField = (jobId: string, index: number, field: string, value: string | null) =>
  api.patch(`/scraper/jobs/${jobId}/update-field`, { index, field, value })

// ── Templates ─────────────────────────────────────────────────────────────────
export const getTemplates = () => api.get('/templates')
export const createTemplate = (data: Record<string, unknown>) => api.post('/templates', data)
export const updateTemplate = (id: string, data: Record<string, unknown>) => api.put(`/templates/${id}`, data)
export const deleteTemplate = (id: string) => api.delete(`/templates/${id}`)

// ── Email Scheduler ───────────────────────────────────────────────────────────
export const scheduleEmail = (data: Record<string, unknown>) => api.post('/emails/schedule', data)
export const getScheduledEmails = () => api.get('/emails/scheduled')
export const processScheduledEmails = () => api.post('/emails/process_scheduled')
export const getEmailOpenStatus = (leadId: string) => api.get(`/emails/open_status/${leadId}`)

// ── Reports ───────────────────────────────────────────────────────────────────
export const exportCsv = () => api.get('/reports/export', { responseType: 'blob' })
export const exportExcel = () => api.get('/reports/export_excel', { responseType: 'blob' })
export const getSalesPerformance = (userId?: string) =>
  api.get('/reports/sales_performance', { params: userId ? { user_id: userId } : {} })

// ── AI Enrich / Pipeline ──────────────────────────────────────────────────────
export const enrichCompany = (company_name: string, lead_id: string) =>
  api.post('/ai/enrich', { company_name, lead_id })
export const getAiPipelineHealth = () => api.post('/ai/pipeline_health')
export const getPipelineHealthCached = (refresh = false) =>
  api.get('/stats/pipeline_health', { params: { refresh } })


// ── Users (for admin) ─────────────────────────────────────────────────────────
export const getUsers = () => api.get('/auth/users')
export const createUser = (data: { name: string; email: string; password: string; role: string }) =>
  api.post('/auth/users', data)
export const updateUser = (id: string, data: { name?: string; role?: string; password?: string; team_id?: string | null }) =>
  api.put(`/auth/users/${id}`, data)
export const deleteUser = (id: string) => api.delete(`/auth/users/${id}`)

// ── Teams ─────────────────────────────────────────────────────────────────────
export const getTeams = () => api.get('/teams')
export const createTeam = (data: { name: string }) => api.post('/teams', data)
export const updateTeam = (id: string, data: { name: string }) => api.put(`/teams/${id}`, data)
export const deleteTeam = (id: string) => api.delete(`/teams/${id}`)
export const getTeamMembers = (id: string) => api.get(`/teams/${id}/members`)

// ── Contacts ──────────────────────────────────────────────────────────────────
export const getContacts = (leadId: string) => api.get(`/leads/${leadId}/contacts`)
export const createContact = (leadId: string, data: Record<string, unknown>) =>
  api.post(`/leads/${leadId}/contacts`, data)
export const updateContact = (id: string, data: Record<string, unknown>) =>
  api.put(`/contacts/${id}`, data)
export const deleteContact = (id: string) => api.delete(`/contacts/${id}`)
export const setContactPrimary = (id: string) => api.post(`/contacts/${id}/set_primary`)

// ── Tags ──────────────────────────────────────────────────────────────────────
export const getTags = () => api.get('/tags')
export const createTag = (data: { name: string; color: string }) => api.post('/tags', data)
export const deleteTag = (id: string) => api.delete(`/tags/${id}`)
export const getLeadTags = (leadId: string) => api.get(`/leads/${leadId}/tags`)
export const addLeadTags = (leadId: string, tag_ids: string[]) =>
  api.post(`/leads/${leadId}/tags`, { tag_ids })
export const removeLeadTag = (leadId: string, tagId: string) =>
  api.delete(`/leads/${leadId}/tags/${tagId}`)

// ── Attachments ───────────────────────────────────────────────────────────────
export const getAttachments = (leadId: string) => api.get(`/leads/${leadId}/attachments`)
export const addAttachment = (leadId: string, data: {
  filename?: string
  file_data?: string
  file_size?: number
  file_type?: string
  drive_url?: string
  drive_name?: string
}) => api.post(`/leads/${leadId}/attachments`, data)
export const uploadAttachment = addAttachment
export const downloadAttachment = (attachmentId: string) =>
  api.get(`/attachments/${attachmentId}/download`, { responseType: 'blob' })
export const deleteAttachment = (attachmentId: string) =>
  api.delete(`/attachments/${attachmentId}`)


// ── A/B Tests ─────────────────────────────────────────────────────────────────
export const getABTests = () => api.get('/ab_tests')
export const createABTest = (data: Record<string, unknown>) => api.post('/ab_tests', data)
export const sendABTest = (id: string, lead_ids: string[]) =>
  api.post(`/ab_tests/${id}/send`, { lead_ids })
export const getABTestResults = (id: string) => api.get(`/ab_tests/${id}/results`)
export const updateABTest = (id: string, data: Record<string, unknown>) =>
  api.patch(`/ab_tests/${id}`, data)

// ── Webhooks ──────────────────────────────────────────────────────────────────
export const getWebhooks = () => api.get('/webhooks')
export const createWebhook = (data: Record<string, unknown>) => api.post('/webhooks', data)
export const updateWebhook = (id: string, data: Record<string, unknown>) =>
  api.put(`/webhooks/${id}`, data)
export const deleteWebhook = (id: string) => api.delete(`/webhooks/${id}`)
export const testWebhook = (id: string) => api.post(`/webhooks/${id}/test`)
export const getWebhookLogs = (id: string) => api.get(`/webhooks/${id}/logs`)

// ── Notifications ─────────────────────────────────────────────────────────────
export const getNotificationSettings = () => api.get('/notifications/settings')
export const testNotification = (message?: string) =>
  api.post('/notifications/test', { message })

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getHeatmap = () => api.get('/analytics/heatmap')
export const getBestTime = () => api.get('/analytics/best_time')

// ── Keyword Trackers ──────────────────────────────────────────────────────────
export const getKeywordTrackers = () => api.get('/keyword_trackers')
export const createKeywordTracker = (data: Record<string, unknown>) =>
  api.post('/keyword_trackers', data)
export const deleteKeywordTracker = (id: string) => api.delete(`/keyword_trackers/${id}`)
export const checkKeywords = (id: string) => api.post(`/keyword_trackers/${id}/check`)

// ── Weekly Reports ────────────────────────────────────────────────────────────
export const generateWeeklyReport = () => api.get('/reports/weekly')
export const getWeeklyReportHistory = () => api.get('/reports/weekly/history')
export const getWeeklyReport = (id: string) => api.get(`/reports/weekly/${id}`)
export const exportReportPdf = (id?: string) =>
  api.post('/reports/weekly/export_pdf', null, { params: id ? { report_id: id } : {} })

// ── Round 4: Cadence 波段引擎 ─────────────────────────────────────────────────
export const getCadences = () => api.get('/cadences')
export const createCadence = (data: Record<string, unknown>) => api.post('/cadences', data)
export const getCadence = (id: string) => api.get(`/cadences/${id}`)
export const updateCadence = (id: string, data: Record<string, unknown>) => api.put(`/cadences/${id}`, data)
export const deleteCadence = (id: string) => api.delete(`/cadences/${id}`)
export const getDueSteps = () => api.get('/cadences/due')
export const enrollCadence = (cadenceId: string, lead_ids: string[]) =>
  api.post(`/cadences/${cadenceId}/enroll`, { lead_ids })
export const getCadenceEnrollments = (cadenceId: string) =>
  api.get(`/cadences/${cadenceId}/enrollments`)
export const advanceEnrollment = (enrollmentId: string, note?: string) =>
  api.post(`/cadences/enrollments/${enrollmentId}/advance`, { note })
export const skipStep = (enrollmentId: string, note?: string) =>
  api.post(`/cadences/enrollments/${enrollmentId}/skip_step`, { note })
export const pauseEnrollment = (enrollmentId: string) =>
  api.post(`/cadences/enrollments/${enrollmentId}/pause`)
export const resumeEnrollment = (enrollmentId: string) =>
  api.post(`/cadences/enrollments/${enrollmentId}/resume`)
export const getLeadCadences = (leadId: string) => api.get(`/cadences/lead/${leadId}`)

// ── Round 4: 通話記錄 ──────────────────────────────────────────────────────────
export const getCalls = (leadId: string) => api.get(`/leads/${leadId}/calls`)
export const createCall = (leadId: string, data: Record<string, unknown>) =>
  api.post(`/leads/${leadId}/calls`, data)
export const getCallStats = () => api.get('/calls/stats')

// ── Round 4: 互動熱度 ──────────────────────────────────────────────────────────
export const recalcEngagement = (leadId: string) =>
  api.post(`/leads/${leadId}/recalc_engagement`)
export const recalcEngagementAll = () => api.post('/leads/recalc_engagement/all')

// ── Round 4: Gmail 回覆偵測 ───────────────────────────────────────────────────
export const checkGmailReplies = () => api.post('/gmail/check_replies')

// ── Round 4: 報告 ─────────────────────────────────────────────────────────────
export const getCampaignSummary = () => api.get('/reports/campaign_summary')
export const exportDeliveryExcel = () => api.get('/reports/delivery', { responseType: 'blob' })
export const getMonthlyPdf = () => api.get('/reports/monthly_pdf')

// ── Round 5: ICP Profiles ──────────────────────────────────────────────────────
export const getICPs = () => api.get('/icp')
export const createICP = (data: Record<string, unknown>) => api.post('/icp', data)
export const updateICP = (id: string, data: Record<string, unknown>) => api.patch(`/icp/${id}`, data)
export const deleteICP = (id: string) => api.delete(`/icp/${id}`)

// ── Round 6: 含金量分析 ───────────────────────────────────────────────────────
export const analyzeSignals = (lead_id: string, website_url?: string) =>
  api.post(`/leads/${lead_id}/signals/analyze`, { website_url })
export const batchAnalyzeSignals = (lead_ids?: string[], all_with_website?: boolean) =>
  api.post('/leads/signals/batch-analyze', { lead_ids: lead_ids || [], all_with_website: all_with_website || false })

// ── Round 6: AI 客製化 Email ──────────────────────────────────────────────────
export const generateEmail = (data: {website_url: string, product: string, lead_id?: string, tone?: string}) =>
  api.post('/ai/generate-email', data)

// ── 提案信生成 ─────────────────────────────────────────────────────────────────
export const generateProposal = (data: { lead_id: string; product: string; tone?: string }) =>
  api.post('/ai/generate-proposal', data)
