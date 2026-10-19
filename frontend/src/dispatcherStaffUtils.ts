import { z } from 'zod'

const phonePattern = /^\+?[0-9\s()-]{7,20}$/

export const staffCreateSchema = z.object({
  phone: z.string().trim().regex(phonePattern, 'Telefon raqamini to‘g‘ri kiriting.'),
  password: z.string().min(8, 'Parol kamida 8 belgidan iborat bo‘lsin.'),
})

export const staffEditSchema = z.object({
  phone: z.string().trim().regex(phonePattern, 'Telefon raqamini to‘g‘ri kiriting.'),
})

export const staffPasswordResetSchema = z.object({
  password: z.string().min(8, 'Yangi parol kamida 8 belgidan iborat bo‘lsin.'),
  password_confirm: z.string().min(8, 'Parolni qayta kiriting.'),
}).refine((values) => values.password === values.password_confirm, {
  message: 'Parollar bir-biriga mos kelmadi.',
  path: ['password_confirm'],
})

export type DispatcherStaff = {
  id: number
  phone: string
  role: 'company_admin' | 'driver'
  is_active: boolean
  is_blocked: boolean
}

export type StaffCreateValues = z.infer<typeof staffCreateSchema>
export type StaffEditValues = z.infer<typeof staffEditSchema>
export type StaffPasswordResetValues = z.infer<typeof staffPasswordResetSchema>

export function filterCompanyStaff(
  staff: DispatcherStaff[],
  search: string,
  status: 'all' | 'active' | 'inactive',
) {
  const query = search.trim().toLocaleLowerCase('uz-UZ')
  return staff.filter((member) => {
    if (member.role !== 'company_admin') return false
    const active = member.is_active && !member.is_blocked
    const matchesStatus = status === 'all' ||
      (status === 'active' ? active : !active)
    return matchesStatus && (!query || member.phone.toLocaleLowerCase('uz-UZ').includes(query))
  })
}

export function buildStaffPayload(values: StaffCreateValues | StaffEditValues) {
  return { phone: values.phone.trim() }
}

export function buildPasswordResetPayload(values: StaffPasswordResetValues) {
  return {
    password: values.password,
    password_confirm: values.password_confirm,
  }
}
