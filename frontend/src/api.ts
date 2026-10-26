import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

export type UserRole = 'super_admin' | 'company_admin' | 'driver' | 'shop_owner'

export type AuthUser = {
  id: number
  phone: string
  role: UserRole
  company_id: number | null
}

export type AuthResponse = {
  access: string
  user: AuthUser
}

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
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
    csrfInFlight = axios
      .get<{ csrfToken: string }>('/api/auth/csrf/', { withCredentials: true })
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
    refreshInFlight = getCsrfToken()
      .then((token) =>
        axios.post<{ access: string }>('/api/auth/refresh/', null, {
          withCredentials: true,
          headers: { 'X-CSRFToken': token },
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
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string; account?: string; phone?: string; password?: string; code?: string }
      | undefined
    if (typeof data?.detail === 'string') return data.detail
    for (const key of ['account', 'phone', 'password', 'code'] as const) {
      const value = data?.[key]
      if (typeof value === 'string') return value
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    }
  }
  return fallback
}

export default api
