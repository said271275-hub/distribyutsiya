import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, LoaderCircle, Pencil, Plus, Search, ShieldCheck, UserRound, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import api, { apiErrorMessage } from './api'
import { useAuth } from './useAuth'
import {
  buildPasswordResetPayload,
  buildStaffPayload,
  filterCompanyStaff,
  staffCreateSchema,
  staffEditSchema,
  staffPasswordResetSchema,
  type DispatcherStaff,
  type StaffCreateValues,
  type StaffEditValues,
  type StaffPasswordResetValues,
} from './dispatcherStaffUtils'
import './DispatcherStaff.css'

type StaffStatus = { id: number; is_active: boolean; is_blocked: boolean }

const emptyCreate: StaffCreateValues = { phone: '', password: '' }
const emptyEdit: StaffEditValues = { phone: '' }
const emptyPassword: StaffPasswordResetValues = { password: '', password_confirm: '' }
const emptyStaff: DispatcherStaff[] = []

export default function DispatcherStaffPage() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<'all' | 'active' | 'inactive'>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [editingStaff, setEditingStaff] = useState<DispatcherStaff | null>(null)
  const [resettingStaff, setResettingStaff] = useState<DispatcherStaff | null>(null)
  const [pageError, setPageError] = useState('')
  const createForm = useForm<StaffCreateValues>({
    resolver: zodResolver(staffCreateSchema),
    defaultValues: emptyCreate,
  })
  const editForm = useForm<StaffEditValues>({
    resolver: zodResolver(staffEditSchema),
    defaultValues: emptyEdit,
  })
  const passwordForm = useForm<StaffPasswordResetValues>({
    resolver: zodResolver(staffPasswordResetSchema),
    defaultValues: emptyPassword,
  })
  const staffQuery = useQuery({
    queryKey: ['dispatcher-staff'],
    queryFn: async () => (
      await api.get<DispatcherStaff[]>('/v1/admin/staff/')
    ).data,
  })
  const staff = staffQuery.data ?? emptyStaff
  const visibleStaff = useMemo(
    () => filterCompanyStaff(staff, search, status),
    [staff, search, status],
  )

  const refreshStaff = async () => {
    await queryClient.invalidateQueries({ queryKey: ['dispatcher-staff'] })
  }
  const createStaff = useMutation({
    mutationFn: async (values: StaffCreateValues) => (
      await api.post<DispatcherStaff>('/v1/admin/staff/', {
        ...buildStaffPayload(values),
        password: values.password,
        role: 'company_admin',
      })
    ).data,
    onSuccess: async () => {
      setPageError('')
      setShowCreate(false)
      createForm.reset(emptyCreate)
      await refreshStaff()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Xodimni yaratib bo‘lmadi. Qayta urinib ko‘ring.')),
  })
  const updateStaff = useMutation({
    mutationFn: async ({ id, values }: { id: number; values: StaffEditValues }) => (
      await api.patch<DispatcherStaff>(`/v1/admin/staff/${id}/`, buildStaffPayload(values))
    ).data,
    onSuccess: async () => {
      setPageError('')
      setEditingStaff(null)
      await refreshStaff()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Xodim ma’lumotini o‘zgartirib bo‘lmadi.')),
  })
  const changeStaffStatus = useMutation({
    mutationFn: async ({ id, active }: { id: number; active: boolean }) => (
      await api.post<StaffStatus>(
        `/v1/admin/staff/${id}/${active ? 'activate' : 'deactivate'}/`,
        {},
      )
    ).data,
    onSuccess: async () => {
      setPageError('')
      await refreshStaff()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Xodim holatini o‘zgartirib bo‘lmadi.')),
  })
  const resetPassword = useMutation({
    mutationFn: async ({ id, values }: { id: number; values: StaffPasswordResetValues }) => (
      await api.post(`/v1/admin/staff/${id}/reset-password/`, buildPasswordResetPayload(values))
    ).data,
    onSuccess: async () => {
      setPageError('')
      setResettingStaff(null)
      passwordForm.reset(emptyPassword)
      await refreshStaff()
    },
    onError: (failure) => setPageError(apiErrorMessage(failure, 'Xodim parolini tiklab bo‘lmadi.')),
  })

  const openCreate = () => {
    setPageError('')
    createStaff.reset()
    createForm.reset(emptyCreate)
    setShowCreate(true)
  }
  const openEdit = (member: DispatcherStaff) => {
    setPageError('')
    updateStaff.reset()
    editForm.reset({ phone: member.phone })
    setEditingStaff(member)
  }
  const openPasswordReset = (member: DispatcherStaff) => {
    setPageError('')
    resetPassword.reset()
    passwordForm.reset(emptyPassword)
    setResettingStaff(member)
  }
  const submitCreate = createForm.handleSubmit((values) => createStaff.mutate(values))
  const submitEdit = editForm.handleSubmit((values) => {
    if (editingStaff) updateStaff.mutate({ id: editingStaff.id, values })
  })
  const submitPasswordReset = passwordForm.handleSubmit((values) => {
    if (resettingStaff) resetPassword.mutate({ id: resettingStaff.id, values })
  })

  return (
    <section className="dispatcher-staff-page">
      <div className="dispatcher-page-heading dispatcher-staff-heading">
        <div>
          <span className="dispatcher-eyebrow">JAMOA BOSHQARUVI</span>
          <h1>Xodimlar</h1>
          <p>Kompaniya dispetcherlarining hisoblarini boshqaring. Haydovchilar alohida bo‘limda boshqariladi.</p>
        </div>
        <button type="button" className="dispatcher-primary-button" onClick={openCreate}>
          <Plus size={16} /> Xodim qo‘shish
        </button>
      </div>

      {pageError && <div className="dispatcher-staff-error" role="alert">{pageError}</div>}

      <section className="dispatcher-card dispatcher-staff-card">
        <div className="dispatcher-staff-toolbar">
          <label className="dispatcher-staff-search">
            <Search size={16} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Telefon raqami bo‘yicha qidirish"
              aria-label="Xodimlarni qidirish"
            />
            {search && <button type="button" aria-label="Qidiruvni tozalash" onClick={() => setSearch('')}><X size={14} /></button>}
          </label>
          <label className="dispatcher-staff-filter">
            <span>Holati</span>
            <select value={status} onChange={(event) => setStatus(event.target.value as typeof status)}>
              <option value="all">Barcha holatlar</option>
              <option value="active">Faol</option>
              <option value="inactive">Faolsiz</option>
            </select>
          </label>
        </div>

        {staffQuery.isLoading ? (
          <div className="dispatcher-loading" role="status"><span /> Xodimlar yuklanmoqda…</div>
        ) : staffQuery.isError ? (
          <div className="dispatcher-error-state" role="alert">
            <p>{apiErrorMessage(staffQuery.error, 'Xodimlar ro‘yxatini yuklab bo‘lmadi.')}</p>
            <button type="button" onClick={() => void staffQuery.refetch()}>Qayta urinish</button>
          </div>
        ) : visibleStaff.length ? (
          <div className="dispatcher-table-scroll">
            <table className="dispatcher-orders-table dispatcher-staff-table">
              <thead><tr><th>Telefon raqami</th><th>Vazifasi</th><th>Holati</th><th>Amallar</th></tr></thead>
              <tbody>
                {visibleStaff.map((member) => {
                  const active = member.is_active && !member.is_blocked
                  const isSelf = member.id === user?.id
                  return (
                    <tr key={member.id}>
                      <td><strong>{member.phone}</strong>{isSelf && <small>Joriy hisob</small>}</td>
                      <td>Dispetcher / kompaniya administratori</td>
                      <td><span className={`dispatcher-status ${active ? 'dispatcher-status-confirmed' : 'dispatcher-status-cancelled'}`}>{active ? 'Faol' : 'Faolsiz'}</span></td>
                      <td>
                        {isSelf ? (
                          <span className="dispatcher-staff-self-note">O‘z hisobingizni bu yerdan o‘zgartira olmaysiz</span>
                        ) : (
                          <div className="dispatcher-staff-actions">
                            <button type="button" className="dispatcher-order-action" aria-label={`${member.phone} tahrirlash`} onClick={() => openEdit(member)}>
                              <Pencil size={14} /> Tahrirlash
                            </button>
                            <button type="button" className="dispatcher-order-action" aria-label={`${member.phone} parolini tiklash`} onClick={() => openPasswordReset(member)}>
                              <KeyRound size={14} /> Parolni tiklash
                            </button>
                            <button
                              type="button"
                              className={`dispatcher-order-action ${active ? 'dispatcher-order-action-danger' : 'dispatcher-order-confirm'}`}
                              disabled={changeStaffStatus.isPending}
                              aria-label={`${member.phone} ${active ? 'faolsizlantirish' : 'faollashtirish'}`}
                              onClick={() => {
                                const title = active ? 'faolsizlantirilsinmi?' : 'faollashtirilsinmi?'
                                if (window.confirm(`${member.phone} xodimi ${title} Hisob butunlay o‘chirilmaydi.`)) {
                                  changeStaffStatus.mutate({ id: member.id, active: !active })
                                }
                              }}
                            >
                              <ShieldCheck size={14} /> {active ? 'Faolsizlantirish' : 'Faollashtirish'}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="dispatcher-empty"><UserRound size={22} /><strong>Xodimlar topilmadi</strong><span>Qidiruvni yoki holat filtrini o‘zgartiring.</span></div>
        )}
        <div className="dispatcher-staff-footer">{visibleStaff.length} ta dispetcher/admin</div>
      </section>

      {showCreate && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !createStaff.isPending) setShowCreate(false)
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-staff-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-staff-create-title"
            onSubmit={(event) => void submitCreate(event)}
          >
            <div className="dispatcher-staff-form-heading">
              <h2 id="dispatcher-staff-create-title">Xodim qo‘shish</h2>
              <button type="button" aria-label="Oynani yopish" disabled={createStaff.isPending} onClick={() => setShowCreate(false)}><X size={17} /></button>
            </div>
            <p>Yangi xodim faqat kompaniya administratori orqali yaratiladi.</p>
            <label><span>Telefon raqami</span><input {...createForm.register('phone')} autoComplete="tel" />{createForm.formState.errors.phone && <small role="alert">{createForm.formState.errors.phone.message}</small>}</label>
            <label><span>Vaqtinchalik parol</span><input {...createForm.register('password')} type="password" autoComplete="new-password" />{createForm.formState.errors.password && <small role="alert">{createForm.formState.errors.password.message}</small>}</label>
            <label><span>Vazifasi</span><input value="Dispetcher / kompaniya administratori" readOnly /></label>
            {createStaff.isError && <p className="dispatcher-staff-form-error" role="alert">{apiErrorMessage(createStaff.error, 'Xodimni yaratib bo‘lmadi.')}</p>}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={createStaff.isPending} onClick={() => setShowCreate(false)}>Bekor qilish</button>
              <button type="submit" className="dispatcher-primary-button" disabled={createStaff.isPending}>
                {createStaff.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : <Plus size={15} />} Yaratish
              </button>
            </div>
          </form>
        </div>
      )}

      {editingStaff && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !updateStaff.isPending) setEditingStaff(null)
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-staff-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-staff-edit-title"
            onSubmit={(event) => void submitEdit(event)}
          >
            <div className="dispatcher-staff-form-heading">
              <h2 id="dispatcher-staff-edit-title">Xodimni tahrirlash</h2>
              <button type="button" aria-label="Oynani yopish" disabled={updateStaff.isPending} onClick={() => setEditingStaff(null)}><X size={17} /></button>
            </div>
            <label><span>Telefon raqami</span><input {...editForm.register('phone')} autoComplete="tel" />{editForm.formState.errors.phone && <small role="alert">{editForm.formState.errors.phone.message}</small>}</label>
            {updateStaff.isError && <p className="dispatcher-staff-form-error" role="alert">{apiErrorMessage(updateStaff.error, 'Xodim ma’lumotini o‘zgartirib bo‘lmadi.')}</p>}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={updateStaff.isPending} onClick={() => setEditingStaff(null)}>Bekor qilish</button>
              <button type="submit" className="dispatcher-primary-button" disabled={updateStaff.isPending}>
                {updateStaff.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : <Pencil size={15} />} Saqlash
              </button>
            </div>
          </form>
        </div>
      )}

      {resettingStaff && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !resetPassword.isPending) setResettingStaff(null)
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-staff-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-staff-password-title"
            onSubmit={(event) => void submitPasswordReset(event)}
          >
            <div className="dispatcher-staff-form-heading">
              <h2 id="dispatcher-staff-password-title">Xodim parolini tiklash</h2>
              <button type="button" aria-label="Oynani yopish" disabled={resetPassword.isPending} onClick={() => setResettingStaff(null)}><X size={17} /></button>
            </div>
            <p>{resettingStaff.phone} uchun yangi parol belgilang. Avvalgi kirishlar bekor qilinadi.</p>
            <label><span>Yangi parol</span><input {...passwordForm.register('password')} type="password" autoComplete="new-password" />{passwordForm.formState.errors.password && <small role="alert">{passwordForm.formState.errors.password.message}</small>}</label>
            <label><span>Yangi parolni takrorlang</span><input {...passwordForm.register('password_confirm')} type="password" autoComplete="new-password" />{passwordForm.formState.errors.password_confirm && <small role="alert">{passwordForm.formState.errors.password_confirm.message}</small>}</label>
            {resetPassword.isError && <p className="dispatcher-staff-form-error" role="alert">{apiErrorMessage(resetPassword.error, 'Xodim parolini tiklab bo‘lmadi.')}</p>}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={resetPassword.isPending} onClick={() => setResettingStaff(null)}>Bekor qilish</button>
              <button type="submit" className="dispatcher-primary-button" disabled={resetPassword.isPending}>
                {resetPassword.isPending ? <LoaderCircle className="dispatcher-spinning" size={15} /> : <KeyRound size={15} />} Parolni saqlash
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}
