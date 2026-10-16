import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { Controller, useForm, type Control } from 'react-hook-form'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { useAuth } from './useAuth'
import api, { apiErrorMessage, type UserRole } from './api'
import { canAccessRoles, roleHomes } from './roleAccess'
import './App.css'

const ShopPanel = lazy(() => import('./ShopPanel'))

const phoneSchema = z
  .string()
  .refine((value) => value.replace(/\D/g, '').replace(/^998/, '').length === 9, {
    message: 'O‘zbekiston telefon raqamini to‘liq kiriting.',
  })

const loginSchema = z.object({
  phone: phoneSchema,
  password: z.string().min(1, 'Parolni kiriting.'),
})

const registerSchema = z.object({
  phone: phoneSchema,
  code: z.string().regex(/^\d{6}$/, '6 xonali SMS kodni kiriting.'),
  password: z.string().min(8, 'Parol kamida 8 ta belgidan iborat bo‘lsin.'),
})

const deletionSchema = z
  .object({
    reason: z.enum(['store_closed', 'moved', 'not_needed', 'other']),
    reason_other: z.string().optional(),
    password: z.string().min(1, 'Parolingizni kiriting.'),
  })
  .refine((value) => value.reason !== 'other' || Boolean(value.reason_other?.trim()), {
    path: ['reason_other'],
    message: 'Sababni qisqacha yozing.',
  })

type LoginValues = z.infer<typeof loginSchema>
type RegisterValues = z.infer<typeof registerSchema>
type DeletionValues = z.infer<typeof deletionSchema>

const roleLabels: Record<UserRole, string> = {
  super_admin: 'Tizim administratori',
  company_admin: 'Kompaniya administratori',
  driver: 'Haydovchi',
  shop_owner: 'Do‘kon egasi',
}

function DevOtpBadge() {
  return import.meta.env.DEV ? (
    <span className="dev-otp-badge" role="status">SINOV REJIMI</span>
  ) : null
}

function formatPhoneInput(value: string) {
  let digits = value.replace(/\D/g, '')
  if (digits.startsWith('998')) digits = digits.slice(3)
  digits = digits.slice(0, 9)
  const groups = [digits.slice(0, 2), digits.slice(2, 5), digits.slice(5, 7), digits.slice(7, 9)]
  const formatted = groups.filter(Boolean).join(' ')
  return formatted ? `+998 ${formatted}` : ''
}

function normalizePhone(value: string) {
  const digits = value.replace(/\D/g, '')
  return digits.startsWith('998') ? `+${digits}` : `+998${digits}`
}

function ThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <button
      type="button"
      onClick={() => setDark((value) => !value)}
      className="theme-toggle"
      aria-label={dark ? 'Yorug‘ rejimga o‘tish' : 'Qorong‘i rejimga o‘tish'}
      title={dark ? 'Yorug‘ rejim' : 'Qorong‘i rejim'}
    >
      {dark ? '☀' : '◐'}
    </button>
  )
}

function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link to="/" className={`brand ${inverse ? 'brand-inverse' : ''}`} aria-label="Distribyutsiya bosh sahifa">
      <span className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </span>
      <span>
        <strong>tarqatuv</strong>
        <small>biznesingiz bir joyda</small>
      </span>
    </Link>
  )
}

function AuthShell({ children, mode = 'shop' }: { children: ReactNode; mode?: 'shop' | 'staff' }) {
  return (
    <main className="auth-layout">
      <aside className="auth-story">
        <div className="story-top">
          <Brand inverse />
          <span className="story-version">BIZNES UCHUN PLATFORMА</span>
        </div>

        <div className="story-content">
          <div className="story-eyebrow">
            <span className="eyebrow-dot" />
            {mode === 'staff' ? 'JAMOA UCHUN XAVFSIZ KIRISH' : 'SAVDONGIZNI YANGI BOSQICHGA OLIB CHIQING'}
          </div>
          <h1>
            Har bir yetkazish
            <br />
            ortida <span>ishonch</span> bor.
          </h1>
          <p className="story-copy">
            Buyurtmadan yetkazib berishgacha — kundalik ishingizni tartibli va
            shaffof boshqaring.
          </p>

          <div className="route-card" aria-hidden="true">
            <div className="route-card-head">
              <div>
                <span className="route-overline">BUGUNGI YETKAZISH</span>
                <strong>Guliston yo‘nalishi</strong>
              </div>
              <span className="route-status"><i /> Faol</span>
            </div>
            <div className="route-map">
              <div className="map-grid" />
              <svg viewBox="0 0 440 150" preserveAspectRatio="none">
                <path className="route-line-shadow" d="M18 112 C72 112 67 49 135 63 S220 125 267 78 S341 38 422 54" />
                <path className="route-line" d="M18 112 C72 112 67 49 135 63 S220 125 267 78 S341 38 422 54" />
              </svg>
              <span className="map-pin pin-one"><i /></span>
              <span className="map-pin pin-two"><i /></span>
              <span className="map-pin pin-three"><i /></span>
              <span className="map-pin pin-four"><i /></span>
              <div className="delivery-chip"><b>12</b><span>nuqta</span></div>
            </div>
            <div className="route-foot">
              <span><b>08:30</b> yo‘lga chiqdi</span>
              <span className="route-foot-progress"><i /></span>
              <span>4 ta bajarildi</span>
            </div>
          </div>

          <div className="story-points">
            <span><i>✓</i> Buyurtmalar nazoratda</span>
            <span><i>✓</i> Jamoa bir tizimda</span>
            <span><i>✓</i> Hisob-kitob shaffof</span>
          </div>
        </div>
        <div className="story-bottom">
          <span>© 2026 Tarqatuv</span>
          <span>O‘zbekiston uchun yaratilgan</span>
        </div>
      </aside>

      <section className="auth-panel">
        <div className="auth-panel-top">
          <Brand />
          <ThemeToggle />
        </div>
        <div className="auth-content">{children}</div>
        <div className="auth-panel-footer">
          <span>Davom etish orqali foydalanish shartlariga rozilik bildirasiz.</span>
          <span className="secure-note"><i /> Xavfsiz ulanish</span>
        </div>
      </section>
    </main>
  )
}

function FormField({
  label,
  error,
  children,
  hint,
}: {
  label: string
  error?: string
  children: ReactNode
  hint?: string
}) {
  return (
    <label className="form-field">
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  )
}

function PhoneControl({
  control,
  error,
}: {
  control: Control<LoginValues>
  error?: string
}) {
  return (
    <FormField label="Telefon raqami" error={error} hint="Ro‘yxatdan o‘tgan raqamingizni kiriting">
      <Controller
        control={control}
        name="phone"
        render={({ field }) => (
          <span className="input-wrap">
            <span className="input-prefix">UZ</span>
            <input
              {...field}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="+998 90 123 45 67"
              onChange={(event) => field.onChange(formatPhoneInput(event.target.value))}
              className="form-input phone-input"
            />
          </span>
        )}
      />
    </FormField>
  )
}

function LoginPage({ staff = false }: { staff?: boolean }) {
  const { login, restore, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [restoreMode, setRestoreMode] = useState(false)
  const [formError, setFormError] = useState('')
  const params = new URLSearchParams(location.search)
  const { control, register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<LoginValues>({
      resolver: zodResolver(loginSchema),
      defaultValues: { phone: '', password: '' },
    })

  if (user) return <Navigate to={roleHomes[user.role]} replace />

  const submit = handleSubmit(async (values) => {
    setFormError('')
    try {
      const signedInUser = restoreMode
        ? await restore(normalizePhone(values.phone), values.password)
        : await login(normalizePhone(values.phone), values.password, staff ? 'staff' : 'shop')
      navigate(roleHomes[signedInUser.role], { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, 'Kirish amalga oshmadi. Ma’lumotlarni tekshiring.'))
    }
  })

  return (
    <AuthShell mode={staff ? 'staff' : 'shop'}>
      <div className="auth-heading">
        <DevOtpBadge />
        <span className="section-kicker">{staff ? 'XODIMLAR MAYDONI' : 'XUSH KELIBSIZ'}</span>
        <h2>{restoreMode ? 'Akkauntni tiklash' : staff ? 'Jamoa uchun kirish' : 'Hisobingizga kiring'}</h2>
        <p>
          {restoreMode
            ? '30 kunlik muddat tugamagan bo‘lsa, akkauntingizni qayta faollashtiring.'
            : staff
              ? 'Kompaniya bergan telefon raqami va parolingizdan foydalaning.'
              : 'Ishni davom ettirish uchun telefon raqamingizni kiriting.'}
        </p>
      </div>

      {params.get('registered') && (
        <div className="notice success-notice"><span>✓</span> Akkaunt yaratildi. Endi tizimga kiring.</div>
      )}
      {params.get('deleted') && (
        <div className="notice warning-notice"><span>!</span> Akkaunt o‘chirish jarayonida. 30 kun ichida tiklashingiz mumkin.</div>
      )}

      {!staff && (
        <div className="auth-switch" role="tablist" aria-label="Kirish turi">
          <Link className="auth-tab active-tab" to="/login">Do‘konchi</Link>
          <Link className="auth-tab" to="/staff/login">Xodim</Link>
        </div>
      )}

      <form className="auth-form" onSubmit={submit} noValidate>
        <PhoneControl control={control} error={errors.phone?.message} />
        <FormField label="Parol" error={errors.password?.message}>
          <span className="input-wrap">
            <span className="input-leading" aria-hidden="true">⌑</span>
            <input
              {...register('password')}
              type="password"
              autoComplete={restoreMode ? 'current-password' : staff ? 'current-password' : 'current-password'}
              placeholder="Parolingizni kiriting"
              className="form-input"
            />
          </span>
        </FormField>
        {formError && <div className="form-alert" role="alert">{formError}</div>}
        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? <span className="button-spinner" /> : null}
          {isSubmitting ? 'Tekshirilmoqda…' : restoreMode ? 'Akkauntni tiklash' : 'Kirish'}
          {!isSubmitting && <span aria-hidden="true">→</span>}
        </button>
      </form>

      <div className="auth-extra">
        {!staff && (
          <button type="button" className="text-button" onClick={() => { setRestoreMode(!restoreMode); setFormError('') }}>
            {restoreMode ? 'Kirish sahifasiga qaytish' : 'Akkauntni o‘chirishni bekor qilmoqchimisiz?'}
          </button>
        )}
        {staff ? (
          <p>Jamoaga yangi xodim kerakmi? <span>Administratoringizga murojaat qiling.</span></p>
        ) : !restoreMode ? (
          <p>Hali akkauntingiz yo‘qmi? <Link to="/register">Ro‘yxatdan o‘ting <span>↗</span></Link></p>
        ) : null}
      </div>

      {staff && <div className="staff-access-note"><span>⌑</span> Bu sahifada faqat kompaniya xodimlari kira oladi.</div>}
      <div className="mobile-story-note"><span className="eyebrow-dot" /> Buyurtma va yetkazish boshqaruvi — bir tizimda</div>
    </AuthShell>
  )
}

function RegisterPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'phone' | 'verify'>('phone')
  const [formError, setFormError] = useState('')
  const [sentPhone, setSentPhone] = useState('')
  const { register, control, handleSubmit, formState: { errors, isSubmitting }, getValues } =
    useForm<RegisterValues>({
      resolver: zodResolver(registerSchema),
      defaultValues: { phone: '', code: '', password: '' },
    })

  const sendCode = async () => {
    const phone = getValues('phone')
    const parsed = phoneSchema.safeParse(phone)
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Telefon raqamini tekshiring.')
      return
    }
    setFormError('')
    try {
      await api.post('/auth/register/otp/', { phone: normalizePhone(phone) })
      setSentPhone(normalizePhone(phone))
      setStep('verify')
    } catch (error) {
      setFormError(apiErrorMessage(error, 'SMS kod yuborilmadi. Keyinroq urinib ko‘ring.'))
    }
  }

  const submit = handleSubmit(async (values) => {
    setFormError('')
    try {
      await api.post('/auth/register/', {
        phone: normalizePhone(values.phone),
        code: values.code,
        password: values.password,
      })
      navigate('/login?registered=1', { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, 'Ro‘yxatdan o‘tish amalga oshmadi.'))
    }
  })

  return (
    <AuthShell>
      <div className="auth-heading">
        <DevOtpBadge />
        <span className="section-kicker">DO‘KONCHI UCHUN</span>
        <h2>Yangi akkaunt yarating</h2>
        <p>Bir necha qadamda hisob ochib, tizimdan foydalanishni boshlang.</p>
      </div>
      <div className="step-indicator">
        <span className="step-number active-step">1</span><i className={step === 'verify' ? 'step-line complete-line' : 'step-line'} />
        <span className={`step-number ${step === 'verify' ? 'active-step' : ''}`}>2</span>
        <span className="step-label">{step === 'phone' ? 'Telefon raqami' : 'Tasdiqlash'}</span>
      </div>

      <form className="auth-form register-form" onSubmit={step === 'verify' ? submit : (event) => { event.preventDefault(); void sendCode() }} noValidate>
        <FormField label="Telefon raqami" error={errors.phone?.message} hint="Sizga tasdiqlash kodi yuboramiz">
          <Controller
            control={control}
            name="phone"
            render={({ field }) => (
              <span className="input-wrap">
                <span className="input-prefix">UZ</span>
                <input
                  {...field}
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="+998 90 123 45 67"
                  onChange={(event) => field.onChange(formatPhoneInput(event.target.value))}
                  className="form-input phone-input"
                />
              </span>
            )}
          />
        </FormField>
        {step === 'verify' && (
          <>
            <FormField label="SMS tasdiqlash kodi" error={errors.code?.message} hint={`Kod ${sentPhone} raqamiga yuborildi`}>
              <input
                {...register('code')}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder="••••••"
                className="form-input otp-input"
              />
            </FormField>
            <FormField label="Yangi parol" error={errors.password?.message} hint="Kamida 8 ta belgi">
              <input
                {...register('password')}
                type="password"
                autoComplete="new-password"
                placeholder="Kuchli parol yarating"
                className="form-input"
              />
            </FormField>
          </>
        )}
        {formError && <div className="form-alert" role="alert">{formError}</div>}
        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? <span className="button-spinner" /> : null}
          {isSubmitting ? 'Bajarilmoqda…' : step === 'phone' ? 'SMS kod olish' : 'Akkaunt yaratish'}
          {!isSubmitting && <span aria-hidden="true">→</span>}
        </button>
        {step === 'verify' && (
          <button type="button" className="text-button centered-button" onClick={() => { setStep('phone'); setFormError('') }}>
            Raqamni o‘zgartirish
          </button>
        )}
      </form>
      <div className="auth-extra">
        <p>Akkauntingiz bormi? <Link to="/login">Tizimga kiring <span>↗</span></Link></p>
      </div>
    </AuthShell>
  )
}

function ProfilePage() {
  const { user, completeDeletion } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState('')
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } =
    useForm<DeletionValues>({
      resolver: zodResolver(deletionSchema),
      defaultValues: { reason: 'not_needed', reason_other: '', password: '' },
    })
  const reason = watch('reason')
  const deletion = useQuery({
    queryKey: ['account-deletion'],
    queryFn: async () => (await api.get('/auth/me/deletion/')).data as {
      pending: boolean
      scheduled_for?: string
    },
    enabled: user?.role === 'shop_owner',
  })

  const submit = handleSubmit(async (values) => {
    setFormError('')
    try {
      await api.post('/auth/me/deletion/', values)
      await queryClient.invalidateQueries({ queryKey: ['account-deletion'] })
      completeDeletion()
      navigate('/login?deleted=1', { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, 'So‘rovni yuborib bo‘lmadi.'))
    }
  })

  return (
    <DashboardShell active="profile">
      <div className="page-title-row">
        <div>
          <span className="section-kicker">SOZLAMALAR</span>
          <h1>Profil va xavfsizlik</h1>
          <p>Shaxsiy ma’lumotlaringiz va akkaunt holati.</p>
        </div>
        <span className="profile-avatar">{user?.phone.slice(-2)}</span>
      </div>

      <section className="profile-card">
        <div className="card-title-row">
          <div className="card-icon">◎</div>
          <div><h2>Shaxsiy ma’lumotlar</h2><p>Akkauntingizga bog‘langan ma’lumotlar</p></div>
        </div>
        <dl className="profile-details">
          <div><dt>Telefon raqami</dt><dd>{user?.phone}</dd></div>
          <div><dt>Foydalanuvchi turi</dt><dd><span className="role-pill">{user ? roleLabels[user.role] : ''}</span></dd></div>
          <div><dt>Kompaniya</dt><dd>{user?.company_id ? `Kompaniya #${user.company_id}` : 'Mustaqil do‘kon'}</dd></div>
        </dl>
      </section>

      {user?.role === 'shop_owner' && (
        <section className="danger-card">
          <div className="card-title-row">
            <div className="card-icon danger-icon">!</div>
            <div><h2>Akkauntni o‘chirish</h2><p>So‘rov yuborilgach, akkaunt vaqtincha bloklanadi.</p></div>
          </div>
          {deletion.isLoading ? (
            <div className="loading-row"><span className="button-spinner" /> Holat tekshirilmoqda…</div>
          ) : deletion.data?.pending ? (
            <div className="pending-deletion">
              <span className="pending-icon">◷</span>
              <div>
                <strong>O‘chirish so‘rovi kutilmoqda</strong>
                <p>{deletion.data.scheduled_for ? new Date(deletion.data.scheduled_for).toLocaleString('uz-UZ') : '30 kunlik muddat' } kuni shaxsiy ma’lumotlar anonimlashtiriladi. Bu vaqtgacha kirish sahifasidan akkauntni tiklashingiz mumkin.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="deletion-warning">
                <strong>Davom etishdan oldin</strong>
                <p>Ochiq buyurtmalarni yakunlang va qarzdorlikni yoping. Buyurtma hamda to‘lov tarixi anonim do‘kon nomi bilan saqlanadi.</p>
              </div>
              <form className="deletion-form" onSubmit={submit} noValidate>
                <FormField label="O‘chirish sababi" error={errors.reason?.message}>
                  <select {...register('reason')} className="form-input select-input">
                    <option value="store_closed">Do‘kon yopildi</option>
                    <option value="moved">Ko‘chib ketdim</option>
                    <option value="not_needed">Endi kerak emas</option>
                    <option value="other">Boshqa sabab</option>
                  </select>
                </FormField>
                {reason === 'other' && (
                  <FormField label="Sababni yozing" error={errors.reason_other?.message}>
                    <textarea {...register('reason_other')} className="form-input textarea-input" rows={3} placeholder="Qisqacha tushuntiring" />
                  </FormField>
                )}
                <FormField label="Parol bilan tasdiqlang" error={errors.password?.message}>
                  <input {...register('password')} type="password" autoComplete="current-password" className="form-input" placeholder="Joriy parolingiz" />
                </FormField>
                {formError && <div className="form-alert" role="alert">{formError}</div>}
                <div className="deletion-actions">
                  <button className="danger-button" disabled={isSubmitting} type="submit">
                    {isSubmitting ? <span className="button-spinner" /> : null} O‘chirish so‘rovini yuborish
                  </button>
                  <span>30 kun ichida qayta tiklash mumkin</span>
                </div>
              </form>
            </>
          )}
        </section>
      )}
    </DashboardShell>
  )
}

function DashboardShell({ children, active }: { children: ReactNode; active: string }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [logoutError, setLogoutError] = useState('')
  const signOut = async () => {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      setLogoutError('Chiqishda xatolik yuz berdi. Qayta urinib ko‘ring.')
    }
  }

  return (
    <main className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <Brand />
        <div className="sidebar-divider" />
        <span className="sidebar-label">SHAXSIY KABINET</span>
        <nav className="sidebar-nav">
          <Link to={user ? roleHomes[user.role] : '/login'} className="sidebar-link">
            <span>▦</span> Bosh sahifa
          </Link>
          <Link to="/profile" className={`sidebar-link ${active === 'profile' ? 'sidebar-active' : ''}`}>
            <span>◎</span> Profil va xavfsizlik
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-user">
            <span className="profile-avatar small-avatar">{user?.phone.slice(-2)}</span>
            <span><strong>{user?.phone}</strong><small>{user ? roleLabels[user.role] : ''}</small></span>
          </div>
          {logoutError && <p className="sidebar-error">{logoutError}</p>}
          <button type="button" className="logout-button" onClick={() => void signOut()}>
            <span>↪</span> Tizimdan chiqish
          </button>
        </div>
      </aside>
      <section className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="breadcrumb">Tarqatuv <span>/</span> Profil va xavfsizlik</div>
          <ThemeToggle />
        </header>
        <div className="dashboard-content">{children}</div>
      </section>
    </main>
  )
}

function RoleLandingPage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <DashboardShell active="home">
      <div className="empty-panel">
        <span className="empty-panel-mark">✳</span>
        <span className="section-kicker">SHAXSIY ISH MAYDONI</span>
        <h1>{roleLabels[user.role]}</h1>
        <p>Akkauntingiz faol. Buyurtma, katalog va yetkazish panellari keyingi bosqichda ulanadi.</p>
        <Link className="secondary-button" to="/profile">Profil va xavfsizlik <span>→</span></Link>
      </div>
    </DashboardShell>
  )
}

function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <main className="full-loader"><span className="button-spinner" /> Xavfsiz ulanish tekshirilmoqda…</main>
  }
  if (!user) {
    const staff = location.pathname !== '/shop' && location.pathname !== '/profile'
    return <Navigate to={staff ? '/staff/login' : '/login'} replace state={{ from: location }} />
  }
  if (!canAccessRoles(user.role, roles)) {
    return <Navigate to={roleHomes[user.role]} replace />
  }
  return children
}

function IndexRedirect() {
  const { user, loading } = useAuth()
  if (loading) return <main className="full-loader"><span className="button-spinner" /> Yuklanmoqda…</main>
  return <Navigate to={user ? roleHomes[user.role] : '/login'} replace />
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<IndexRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/staff/login" element={<LoginPage staff />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute roles={['super_admin']}><RoleLandingPage /></ProtectedRoute>} />
      <Route path="/company" element={<ProtectedRoute roles={['company_admin']}><RoleLandingPage /></ProtectedRoute>} />
      <Route path="/driver" element={<ProtectedRoute roles={['driver']}><RoleLandingPage /></ProtectedRoute>} />
      <Route path="/shop/*" element={<ProtectedRoute roles={['shop_owner']}><Suspense fallback={<main className="full-loader">Yuklanmoqda…</main>}><ShopPanel /></Suspense></ProtectedRoute>} />
      <Route path="*" element={<IndexRedirect />} />
    </Routes>
  )
}

export default App
