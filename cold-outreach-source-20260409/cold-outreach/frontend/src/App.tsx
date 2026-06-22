import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthContext, useAuthProvider, useAuth } from '@/hooks/useAuth'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import LoginPage from '@/pages/LoginPage'
import LeadsPage from '@/pages/LeadsPage'
import LeadDetailPage from '@/pages/LeadDetailPage'
import DashboardPage from '@/pages/DashboardPage'
import SequencesPage from '@/pages/SequencesPage'
import TemplatesPage from '@/pages/TemplatesPage'
import SalesPerformancePage from '@/pages/SalesPerformancePage'
import SettingsPage from '@/pages/SettingsPage'
import ABTestPage from '@/pages/ABTestPage'
import AnalyticsPage from '@/pages/AnalyticsPage'
import WeeklyReportPage from '@/pages/WeeklyReportPage'
import CadencePage from '@/pages/CadencePage'
import TodayPage from '@/pages/TodayPage'
import ReportsPage from '@/pages/ReportsPage'
import ICPPage from '@/pages/ICPPage'
import ScraperJobPage from '@/pages/ScraperJobPage'
import ProposalsPage from '@/pages/ProposalsPage'
import ProposalPage from '@/pages/ProposalPage'
import RagicPage from '@/pages/RagicPage'
import Layout from '@/components/Layout'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-muted-foreground">載入中...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const auth = useAuthProvider()

  return (
    <AuthContext.Provider value={auth}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/leads" replace />} />
          <Route path="leads" element={<ErrorBoundary><LeadsPage /></ErrorBoundary>} />
          <Route path="leads/:id" element={<ErrorBoundary><LeadDetailPage /></ErrorBoundary>} />
          <Route path="sequences" element={<ErrorBoundary><SequencesPage /></ErrorBoundary>} />
          <Route path="dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
          <Route path="templates" element={<ErrorBoundary><TemplatesPage /></ErrorBoundary>} />
          <Route path="performance" element={<ErrorBoundary><SalesPerformancePage /></ErrorBoundary>} />
          <Route path="settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
          <Route path="ab-tests" element={<ErrorBoundary><ABTestPage /></ErrorBoundary>} />
          <Route path="analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
          <Route path="reports" element={<ErrorBoundary><WeeklyReportPage /></ErrorBoundary>} />
          <Route path="cadences" element={<ErrorBoundary><CadencePage /></ErrorBoundary>} />
          <Route path="today" element={<ErrorBoundary><TodayPage /></ErrorBoundary>} />
          <Route path="campaign-reports" element={<ErrorBoundary><ReportsPage /></ErrorBoundary>} />
          <Route path="icp" element={<ErrorBoundary><ICPPage /></ErrorBoundary>} />
          <Route path="scraper/:id" element={<ErrorBoundary><ScraperJobPage /></ErrorBoundary>} />
          <Route path="proposals" element={<ErrorBoundary><ProposalsPage /></ErrorBoundary>} />
          <Route path="proposal" element={<ErrorBoundary><ProposalPage /></ErrorBoundary>} />
          <Route path="ragic" element={<ErrorBoundary><RagicPage /></ErrorBoundary>} />
        </Route>
        <Route path="*" element={<Navigate to="/leads" replace />} />
      </Routes>
    </AuthContext.Provider>
  )
}
