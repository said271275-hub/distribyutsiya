import { describe, expect, it } from 'vitest'
import {
  buildPasswordResetPayload,
  buildStaffPayload,
  filterCompanyStaff,
  staffCreateSchema,
  staffEditSchema,
  staffPasswordResetSchema,
  type DispatcherStaff,
} from './dispatcherStaffUtils'

const staff: DispatcherStaff[] = [
  { id: 1, phone: '+998900000001', role: 'company_admin', is_active: true, is_blocked: false },
  { id: 2, phone: '+998900000002', role: 'company_admin', is_active: false, is_blocked: true },
  { id: 3, phone: '+998900000003', role: 'driver', is_active: true, is_blocked: false },
]

describe('dispetcher xodim yordamchilari', () => {
  it('xodim yaratish va tahrirlashda telefon raqamini tekshiradi', () => {
    expect(staffCreateSchema.safeParse({
      phone: '+998900000004',
      password: 'vaqtinchalik123',
    }).success).toBe(true)
    expect(staffCreateSchema.safeParse({
      phone: 'noto‘g‘ri',
      password: 'qisqa',
    }).success).toBe(false)
    expect(staffEditSchema.safeParse({ phone: '+998900000004' }).success).toBe(true)
    expect(staffEditSchema.safeParse({ phone: 'xato' }).success).toBe(false)
  })

  it('xodim yaratish uchun kompaniya admini rolini API shaklida tayyorlaydi', () => {
    expect(buildStaffPayload({ phone: ' +998900000004 ', password: 'vaqtinchalik123' })).toEqual({
      phone: '+998900000004',
    })
  })

  it('xodimlar ro‘yxatida haydovchilarni takror ko‘rsatmaydi', () => {
    expect(filterCompanyStaff(staff, '', 'all')).toEqual(staff.slice(0, 2))
    expect(filterCompanyStaff(staff, '000002', 'inactive')).toEqual([staff[1]])
    expect(filterCompanyStaff(staff, '000001', 'inactive')).toEqual([])
  })

  it('parolni tiklashda uzunlik va takroriy parol mosligini tekshiradi', () => {
    const valid = {
      password: 'Yangi-Xavfsiz-939!',
      password_confirm: 'Yangi-Xavfsiz-939!',
    }
    expect(staffPasswordResetSchema.safeParse(valid).success).toBe(true)
    expect(staffPasswordResetSchema.safeParse({
      ...valid,
      password_confirm: 'boshqa-parol',
    }).success).toBe(false)
    expect(buildPasswordResetPayload(valid)).toEqual(valid)
  })
})
