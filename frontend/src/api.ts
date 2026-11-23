import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { readLanguage } from './i18n/storage'
import { translateServerError } from './i18n/serverErrors'

export type UserRole = 'super_admin' | 'company_admin' | 'driver' | 'shop_owner'

export type AuthUser = {
  id: number
  phone: string
  role: UserRole
  company_id: number | null
  must_change_password: boolean
}

export type AuthResponse = {
  access: string
  user: AuthUser
}

const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')

export function formatMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const normalized = url.startsWith('/') ? url : `/${url}`
  return API_BASE_URL ? `${API_BASE_URL}${normalized}` : normalized
}

/**
 * Cloudinary rasmlarini bir xil o'lchamga (kvadrat, kesmasdan) va yengil formatga keltiradi.
 * Cloudinary bo'lmagan yoki allaqachon o'zgartirilgan havolalarga tegmaydi.
 */
export function optimizeImageUrl(url: string | null | undefined, size = 600): string | null {
  if (!url) return null
  const marker = '/image/upload/'
  const at = url.indexOf(marker)
  if (!url.includes('res.cloudinary.com') || at === -1) return url
  const head = url.slice(0, at + marker.length)
  const rest = url.slice(at + marker.length)
  if (rest.split('/')[0].includes(',')) return url
  return `${head}c_limit,w_${size},h_${size},f_auto,q_auto/${rest}`
}

const api = axios.create({
  baseURL: API_BASE_URL ? `${API_BASE_URL}/api` : '/api',
  withCredentials: true,
  timeout: 10000,
})

let accessToken: string | null = null
let refreshInFlight: Promise<string | null> | null = null
let csrfToken: string | null = null
let csrfInFlight: Promise<string> | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

function getCsrfToken() {
  if (!csrfInFlight) {
    const url = API_BASE_URL ? `${API_BASE_URL}/api/auth/csrf/` : '/api/auth/csrf/'
    csrfInFlight = axios
      .get<{ csrfToken: string }>(url, { withCredentials: true, timeout: 8000 })
      .then(({ data }) => {
        csrfToken = data.csrfToken
        return csrfToken
      })
      .finally(() => {
        csrfInFlight = null
      })
  }
  return csrfInFlight
}

function requestRefresh() {
  if (!refreshInFlight) {
    const refreshUrl = API_BASE_URL ? `${API_BASE_URL}/api/auth/refresh/` : '/api/auth/refresh/'
    refreshInFlight = getCsrfToken()
      .then((token) =>
        axios.post<{ access: string }>(refreshUrl, null, {
          withCredentials: true,
          headers: { 'X-CSRFToken': token },
          timeout: 8000,
        }),
      )
      .then(({ data }) => {
        setAccessToken(data.access)
        return data.access
      })
      .catch((error: AxiosError) => {
        setAccessToken(null)
        window.dispatchEvent(new CustomEvent('auth:expired', {
          detail: { offline: !error.response, status: error.response?.status },
        }))
        return null
      })
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

api.interceptors.request.use(async (config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  if (['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase() ?? '')) {
    config.headers['X-CSRFToken'] = await getCsrfToken()
  }
  return config
})

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean }

const publicAuthPaths = [
  '/auth/login/',
  '/auth/staff/login/',
  '/auth/register/',
  '/auth/register/otp/',
  '/auth/restore/',
  '/auth/restore/otp/',
  '/auth/password/reset/',
  '/auth/password/reset/otp/',
  '/auth/refresh/',
]

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined
    if (
      error.response?.status !== 401 ||
      !original ||
      original._retry ||
      publicAuthPaths.some((path) => original.url?.endsWith(path))
    ) {
      return Promise.reject(error)
    }

    original._retry = true
    const refreshed = await requestRefresh()
    if (!refreshed) {
      return Promise.reject(error)
    }
    original.headers.Authorization = `Bearer ${refreshed}`
    return api(original)
  },
)

export function apiErrorMessage(error: unknown, fallback = 'So‘rovni bajarib bo‘lmadi.') {
  const language = readLanguage(localStorage)
  const localize = (message: string) => translateServerError(message, language) ?? message
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string; account?: string; phone?: string; password?: string; code?: string }
      | undefined
    if (typeof data?.detail === 'string') return localize(data.detail)
    for (const key of ['account', 'phone', 'password', 'code'] as const) {
      const value = data?.[key]
      if (typeof value === 'string') return localize(value)
      if (Array.isArray(value) && typeof value[0] === 'string') return localize(value[0])
    }
  }
  return fallback
}

export default api
