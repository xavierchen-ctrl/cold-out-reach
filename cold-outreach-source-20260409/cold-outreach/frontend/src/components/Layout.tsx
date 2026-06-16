import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { LayoutDashboard, Users, LogOut, Mail, FileText, TrendingUp, Settings, FlaskConical, BarChart3, FileBarChart2, CalendarCheck, Target, BarChart2, Crosshair, Menu, X, Presentation } from 'lucide-react'

export default function Layout() {
  const { user, signOut } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const SidebarContent = () => (
    <>
      <div className="px-5 py-4 border-b flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold text-gray-900">Cold Outreach</h1>
          <p className="text-xs text-muted-foreground mt-0.5">{user?.name}</p>
        </div>
        <button className="lg:hidden" onClick={() => setSidebarOpen(false)}>
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {[
          { to: '/leads', icon: <Users className="w-4 h-4" />, label: '名單管理' },
          { to: '/sequences', icon: <Mail className="w-4 h-4" />, label: '發信序列' },
          { to: '/templates', icon: <FileText className="w-4 h-4" />, label: '信件模板' },
          { to: '/today', icon: <CalendarCheck className="w-4 h-4" />, label: '今日待辦' },
          { to: '/cadences', icon: <Target className="w-4 h-4" />, label: 'Cadence 波段' },
          { to: '/icp', icon: <Crosshair className="w-4 h-4" />, label: 'ICP 設定' },
          { to: '/performance', icon: <TrendingUp className="w-4 h-4" />, label: '績效報告' },
          ...(user?.role === 'admin' ? [{ to: '/dashboard', icon: <LayoutDashboard className="w-4 h-4" />, label: '業績 Dashboard' }] : []),
          { to: '/analytics', icon: <BarChart3 className="w-4 h-4" />, label: '智能分析' },
          { to: '/reports', icon: <FileBarChart2 className="w-4 h-4" />, label: 'AI 週報' },
          { to: '/proposal', icon: <Presentation className="w-4 h-4" />, label: '提案生成' },
          { to: '/settings', icon: <Settings className="w-4 h-4" />, label: '設定' },
        ].map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-primary text-primary-foreground' : 'text-gray-700 hover:bg-gray-100'}`
            }
          >
            {item.icon} {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-3 py-4 border-t">
        <Button variant="ghost" size="sm" className="w-full justify-start gap-2" onClick={signOut}>
          <LogOut className="w-4 h-4" /> 登出
        </Button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Mobile overlay sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
        <aside className="fixed left-0 top-0 h-full w-64 bg-white shadow-xl flex flex-col">
          <SidebarContent />
        </aside>
      </div>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex lg:w-56 bg-white border-r flex-col">
        <SidebarContent />
      </aside>

      {/* Main content wrapper */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top header */}
        <header className="lg:hidden bg-white border-b px-4 py-3 flex items-center gap-3 flex-shrink-0">
          <button onClick={() => setSidebarOpen(true)}>
            <Menu className="w-5 h-5 text-gray-700" />
          </button>
          <h1 className="text-base font-bold text-gray-900">Cold Outreach</h1>
        </header>

        {/* Main */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
