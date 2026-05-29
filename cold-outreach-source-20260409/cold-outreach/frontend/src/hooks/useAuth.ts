import { useState, useEffect, createContext, useContext } from 'react'
import { getMe, logout as apiLogout } from '@/lib/api'
import { User } from '@/types'

// ── DEV BYPASS ────────────────────────────────────────────────────────────────
// 設為 true 可直接跳過登入，使用假的 admin 帳號進入系統
// 上線前請改回 false
const DEV_BYPASS = false

const DEV_USER: User = {
  id: 'dev-admin',
  email: 'dev@local',
  name: 'Dev Admin',
  role: 'admin',
  team_id: null,
  created_at: new Date().toISOString(),
}
// ─────────────────────────────────────────────────────────────────────────────

interface AuthCtx {
  user: User | null
  loading: boolean
  refresh: () => Promise<void>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  refresh: async () => {},
  signOut: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function useAuthProvider(): AuthCtx {
  const [user, setUser] = useState<User | null>(DEV_BYPASS ? DEV_USER : null)
  const [loading, setLoading] = useState(!DEV_BYPASS)

  const refresh = async () => {
    if (DEV_BYPASS) return
    try {
      const res = await getMe()
      setUser(res.data)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const signOut = async () => {
    if (DEV_BYPASS) return
    await apiLogout()
    setUser(null)
    window.location.href = '/login'
  }

  useEffect(() => {
    if (!DEV_BYPASS) refresh()
  }, [])

  return { user, loading, refresh, signOut }
}
