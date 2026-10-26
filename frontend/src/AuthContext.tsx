import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import api, { setAccessToken, type AuthResponse, type AuthUser } from './api'
import { AuthContext, type LoginScope } from './auth-context'
import {
  clearDriverOfflineData,
  getDriverOfflineSession,
  saveDriverOfflineSession,
} from './driverOfflineStore'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const clearAuth = useCallback(() => {
    setAccessToken(null)
    setUser(null)
  }, [])

  const clearDriverShellCache = useCallback(() => {
    if (!('serviceWorker' in navigator)) return
    const controller = navigator.serviceWorker.controller
    if (controller) {
      controller.postMessage({ type: 'CLEAR_DRIVER_APP_CACHE' })
    } else {
      void navigator.serviceWorker.getRegistration().then((registration) => {
        registration?.active?.postMessage({ type: 'CLEAR_DRIVER_APP_CACHE' })
      })
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const restoreSession = async () => {
      if (localStorage.getItem('driver-offline-logout') === '1') {
        if (mounted) setLoading(false)
        return
      }
      try {
        const { data } = await api.post<{ access: string }>('/auth/refresh/')
        setAccessToken(data.access)
        const profile = await api.get<AuthUser>('/auth/me/')
        if (!mounted) return
        setUser(profile.data)
        await saveDriverOfflineSession(profile.data).catch(() => undefined)
      } catch (error) {
        setAccessToken(null)
        const hasHttpResponse = typeof error === 'object'
          && error !== null
          && 'response' in error
          && error.response !== undefined
        const responseStatus = hasHttpResponse
          && typeof error.response === 'object'
          && error.response !== null
          && 'status' in error.response
          ? error.response.status
          : undefined
        if (responseStatus === 401) {
          await clearDriverOfflineData()
          queryClient.removeQueries({ queryKey: ['driver-trips'] })
        }
        const offlineUser = hasHttpResponse
          ? null
          : await getDriverOfflineSession().catch(() => null)
        if (mounted && offlineUser) setUser(offlineUser)
        else if (mounted) clearAuth()
      } finally {
        if (mounted) setLoading(false)
      }
    }
    const onExpired = (event: Event) => {
      const details = (event as CustomEvent<{ offline?: boolean; status?: number }>).detail
      if (details?.offline) {
        void getDriverOfflineSession().then((offlineUser) => {
          if (mounted && offlineUser) setUser(offlineUser)
          else if (mounted) clearAuth()
        }).catch(clearAuth)
        return
      }
      void clearDriverOfflineData()
      queryClient.removeQueries({ queryKey: ['driver-trips'] })
      clearAuth()
    }
    const onOnline = () => void restoreSession()
    const onOffline = async () => {
      if (localStorage.getItem('driver-offline-logout') === '1') return
      const offlineUser = await getDriverOfflineSession().catch(() => null)
      if (mounted && offlineUser) setUser(offlineUser)
    }
    window.addEventListener('auth:expired', onExpired)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    void restoreSession()
    return () => {
      mounted = false
      window.removeEventListener('auth:expired', onExpired)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [clearAuth, queryClient])

  const login = useCallback(
    async (phone: string, password: string, scope: LoginScope) => {
      const path = scope === 'staff' ? '/auth/staff/login/' : '/auth/login/'
      const { data } = await api.post<AuthResponse>(path, { phone, password })
      localStorage.removeItem('driver-offline-logout')
      setAccessToken(data.access)
      setUser(data.user)
      if (data.user.role === 'driver') await saveDriverOfflineSession(data.user).catch(() => undefined)
      else await clearDriverOfflineData()
      return data.user
    },
    [],
  )

  const restore = useCallback(async (phone: string, password: string) => {
    const { data } = await api.post<AuthResponse>('/auth/restore/', { phone, password })
    localStorage.removeItem('driver-offline-logout')
    setAccessToken(data.access)
    setUser(data.user)
    if (data.user.role === 'driver') await saveDriverOfflineSession(data.user).catch(() => undefined)
    else await clearDriverOfflineData()
    return data.user
  }, [])

  const logout = useCallback(async () => {
    const wasOffline = !navigator.onLine
    try {
      if (!wasOffline) await api.post('/auth/logout/')
    } finally {
      if (wasOffline) localStorage.setItem('driver-offline-logout', '1')
      else localStorage.removeItem('driver-offline-logout')
      queryClient.removeQueries({ queryKey: ['driver-trips'] })
      await clearDriverOfflineData()
      clearDriverShellCache()
      clearAuth()
    }
  }, [clearAuth, clearDriverShellCache, queryClient])

  const value = useMemo(
    () => ({ user, loading, login, restore, logout, completeDeletion: clearAuth }),
    [user, loading, login, restore, logout, clearAuth],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
