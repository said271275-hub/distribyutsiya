import { createContext } from 'react'
import type { AuthUser } from './api'

export type LoginScope = 'shop' | 'staff'

export type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  login: (phone: string, password: string, scope: LoginScope) => Promise<AuthUser>
  restore: (phone: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  completeDeletion: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
