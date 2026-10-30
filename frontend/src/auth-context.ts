import { createContext } from 'react'
import type { AuthUser } from './api'

export type LoginScope = 'shop' | 'staff'

export type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  login: (phone: string, password: string, scope: LoginScope) => Promise<AuthUser>
  changePassword: (currentPassword: string, password: string, passwordConfirm: string) => Promise<AuthUser>
  changePhone: (phone: string, code: string) => Promise<AuthUser>
  restore: (phone: string, password: string, code: string) => Promise<AuthUser>
  logout: () => Promise<void>
  completeDeletion: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
