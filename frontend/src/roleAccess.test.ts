import { describe, expect, it } from 'vitest'
import { canAccessRoles, roleHomes } from './roleAccess'

describe('role route access', () => {
  it.each([
    ['super_admin', '/admin'],
    ['company_admin', '/company'],
    ['driver', '/driver'],
    ['shop_owner', '/shop'],
  ] as const)('%s is routed to its own home', (role, home) => {
    expect(roleHomes[role]).toBe(home)
    expect(canAccessRoles(role, [role])).toBe(true)
  })

  it('denies a role that does not match the protected page', () => {
    expect(canAccessRoles('shop_owner', ['company_admin', 'driver'])).toBe(false)
    expect(canAccessRoles('company_admin', ['shop_owner'])).toBe(false)
  })
})
