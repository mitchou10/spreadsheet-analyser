import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { User } from '../types/user'

// The browser talks to the backend directly (not through the Vite/nginx
// origin): the BFF session cookie is scoped to this origin, and CORS on the
// backend explicitly allows it (see KeycloakSettings.FRONTEND_URL).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface AuthMe {
  user_id: string
  email: string
  first_name: string
  last_name: string
  roles: string[]
  is_admin: boolean
}

function toUser(me: AuthMe): User {
  const name = [me.first_name, me.last_name].filter(Boolean).join(' ')
  return { name: name || me.email || me.user_id, email: me.email, isAdmin: me.is_admin }
}

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (redirect?: string) => void
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/me`, { credentials: 'include' })
      setUser(response.ok ? toUser(await response.json()) : null)
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  const login = useCallback((redirect: string = window.location.pathname) => {
    // When API_BASE_URL is empty (same-origin, ingress-routed prod), fall back
    // to window.location.origin so `new URL` gets a valid base. In dev,
    // API_BASE_URL is an absolute URL (http://localhost:8000) and is used as-is.
    const url = new URL(`${API_BASE_URL}/api/auth/login`, window.location.origin)
    url.searchParams.set('redirect', redirect)
    window.location.href = url.toString()
  }, [])

  const logout = useCallback(async () => {
    const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    })
    setUser(null)
    const { redirectUrl } = await response.json()
    window.location.href = redirectUrl
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: user !== null, isLoading, login, logout, refresh: fetchMe }),
    [user, isLoading, login, logout, fetchMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useCurrentUser(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useCurrentUser must be used within an AuthProvider')
  return context
}
