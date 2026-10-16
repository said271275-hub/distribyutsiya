import type { UserRole } from './api'

export const roleHomes: Record<UserRole, string> = {
  super_admin: '/admin',
  company_admin: '/company',
  driver: '/driver',
  shop_owner: '/shop',
}

export function canAccessRoles(role: UserRole, allowedRoles?: readonly UserRole[]) {
  return !allowedRoles || allowedRoles.includes(role)
}
