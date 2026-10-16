import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import api, { setAccessToken, type AuthResponse, type AuthUser } from './api'
import { AuthContext, type LoginScope } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const clearAuth = useCallback(() => {
    setAccessToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    const onExpired = () => clearAuth()
    window.addEventListener('auth:expired', onExpired)
    void api
      .post<{ access: string }>('/auth/refresh/')
      .then(({ data }) => {
        setAccessToken(data.access)
        return api.get<AuthUser>('/auth/me/')
      })
      .then(({ data }) => setUser(data))
      .catch(() => clearAuth())
      .finally(() => setLoading(false))
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [clearAuth])

  const login = useCallback(
    async (phone: string, password: string, scope: LoginScope) => {
      const path = scope === 'staff' ? '/auth/staff/login/' : '/auth/login/'
      const { data } = await api.post<AuthResponse>(path, { phone, password })
      setAccessToken(data.access)
      setUser(data.user)
      return data.user
    },
    [],
  )

  const restore = useCallback(async (phone: string, password: string) => {
    const { data } = await api.post<AuthResponse>('/auth/restore/', { phone, password })
    setAccessToken(data.access)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout/')
    } finally {
      clearAuth()
    }
  }, [clearAuth])

  const value = useMemo(
    () => ({ user, loading, login, restore, logout, completeDeletion: clearAuth }),
    [user, loading, login, restore, logout, clearAuth],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
