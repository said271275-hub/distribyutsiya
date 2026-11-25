import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Controller, useForm, type Control } from 'react-hook-form'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { useAuth } from './useAuth'
import { SimpleThemeToggle } from './SimpleThemeToggle'
import api, { apiErrorMessage, type UserRole } from './api'
import { formatDate } from './i18n/format'
import { LanguageSelect } from './i18n/LanguageSelect'
import { useTranslation } from './i18n/useTranslation'
import type { TranslationKey } from './i18n/catalog'
import { canAccessRoles, roleHomes } from './roleAccess'
import './App.css'

const ShopPanel = lazy(() => import('./ShopPanel'))
const DispatcherPanel = lazy(() => import('./DispatcherPanel'))
const DriverPanel = lazy(() => import('./DriverPanel'))
const LandingChoicePage = lazy(() => import('./LandingChoicePage'))
const CompanyRegisterPage = lazy(() => import('./CompanyRegisterPage'))

type Translate = (key: TranslationKey) => string

const createPhoneSchema = (t: Translate) =>
  z.string().refine(
    (value) => value.replace(/\D/g, '').replace(/^998/, '').length === 9,
    { message: t('error.phoneInvalid') },
  )

const createLoginSchema = (t: Translate) => z.object({
  phone: createPhoneSchema(t),
  password: z.string().min(1, t('error.passwordRequired')),
})

const createRegisterSchema = (t: Translate) => z.object({
  phone: createPhoneSchema(t),
  code: z.string().regex(/^\d{6}$/, t('error.codeInvalid')),
  password: z.string().min(8, t('error.passwordTooShort')),
})

const createDeletionSchema = (t: Translate) => z
  .object({
    reason: z.enum(['store_closed', 'moved', 'not_needed', 'other']),
    reason_other: z.string().optional(),
    password: z.string().min(1, t('error.passwordRequired')),
  })
  .refine((value) => value.reason !== 'other' || Boolean(value.reason_other?.trim()), {
    path: ['reason_other'],
    message: t('error.reasonRequired'),
  })

type LoginValues = z.infer<ReturnType<typeof createLoginSchema>>
type RegisterValues = z.infer<ReturnType<typeof createRegisterSchema>>
type DeletionValues = z.infer<ReturnType<typeof createDeletionSchema>>

const roleLabelKeys: Record<UserRole, TranslationKey> = {
  super_admin: 'auth.role.superAdmin',
  company_admin: 'auth.role.companyAdmin',
  driver: 'auth.role.driver',
  shop_owner: 'auth.role.shopOwner',
}

function DevOtpBadge() {
  const { t } = useTranslation()
  return import.meta.env.DEV ? (
    <span className="dev-otp-badge" role="status">{t('auth.devMode')}</span>
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
  return <SimpleThemeToggle />
}

function Brand({ inverse = false }: { inverse?: boolean }) {
  const { t } = useTranslation()
  return (
    <Link to="/" className={`brand ${inverse ? 'brand-inverse' : ''}`} aria-label={t('brand.home')}>
      <span className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </span>
      <span>
        <strong>tarqatuv</strong>
        <small>{t('brand.tagline')}</small>
      </span>
    </Link>
  )
}

function AuthShell({ children, mode = 'shop' }: { children: ReactNode; mode?: 'shop' | 'staff' }) {
  const { t } = useTranslation()
  return (
    <main className="auth-layout">
      <aside className="auth-story">
        <div className="story-top">
          <Brand inverse />
          <span className="story-version">{t('brand.platform')}</span>
        </div>

        <div className="story-content">
          <div className="story-eyebrow">
            <span className="eyebrow-dot" />
            {t(mode === 'staff' ? 'brand.staffAccess' : 'brand.shopAccess')}
          </div>
          <h1>
            {t('brand.deliveryLead')}
            <br />
            <span>{t('brand.trust')}</span>{t('brand.trustSuffix')}
          </h1>
          <p className="story-copy">{t('brand.story')}</p>

          <div className="route-card" aria-hidden="true">
            <div className="route-card-head">
              <div>
                <span className="route-overline">{t('brand.todayDelivery')}</span>
                <strong>{t('brand.routeName')}</strong>
              </div>
              <span className="route-status"><i /> {t('brand.active')}</span>
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
              <div className="delivery-chip"><b>12</b><span>{t('brand.stopUnit')}</span></div>
            </div>
            <div className="route-foot">
              <span><b>08:30</b> {t('brand.departed')}</span>
              <span className="route-foot-progress"><i /></span>
              <span>{t('brand.completed').replace('{count}', '4')}</span>
            </div>
          </div>

          <div className="story-points">
            <span><i>✓</i> {t('brand.ordersControlled')}</span>
            <span><i>✓</i> {t('brand.teamTogether')}</span>
            <span><i>✓</i> {t('brand.clearAccounting')}</span>
          </div>
        </div>
        <div className="story-bottom">
          <span>{t('brand.copyright')}</span>
          <span>{t('brand.madeForUzbekistan')}</span>
        </div>
      </aside>

      <section className="auth-panel">
        <div className="auth-panel-top">
          <Brand />
          <div className="auth-controls"><LanguageSelect /><ThemeToggle /></div>
        </div>
        <div className="auth-content">{children}</div>
        <div className="auth-panel-footer">
          <span>{t('common.terms')}</span>
          <span className="secure-note"><i /> {t('common.secureConnection')}</span>
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
  t,
}: {
  control: Control<LoginValues>
  error?: string
  t: Translate
}) {
  return (
    <FormField label={t('common.phone')} error={error} hint={t('common.phoneHint')}>
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

const companyRegisterCopy = {
  uz: { question: 'Yangi kompaniya ochmoqchimisiz?', link: 'Kompaniyani ro‘yxatdan o‘tkazish' },
  ru: { question: 'Хотите открыть новую компанию?', link: 'Зарегистрировать компанию' },
} as const

// Bitta umumiy kirish: do‘konchi, kompaniya xodimi va haydovchi shu yerdan kiradi.
// Foydalanuvchi roli bo‘yicha o‘z paneliga yo‘naltiriladi (roleHomes).
function LoginPage() {
  const { t, language } = useTranslation()
  const { login, restore, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [restoreMode, setRestoreMode] = useState(false)
  const [codeRequested, setCodeRequested] = useState(false)
  const [loginCode, setLoginCode] = useState('')
  const [formError, setFormError] = useState('')
  const params = new URLSearchParams(location.search)
  const loginSchema = useMemo(() => createLoginSchema(t), [t])
  const companyCopy = companyRegisterCopy[language === 'ru' ? 'ru' : 'uz']
  const { control, register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<LoginValues>({
      resolver: zodResolver(loginSchema),
      defaultValues: { phone: '', password: '' },
    })

  if (user) {
    return (
      <Navigate
        to={user.must_change_password ? '/password/change' : roleHomes[user.role]}
        replace
      />
    )
  }

  const submit = handleSubmit(async (values) => {
    setFormError('')
    try {
      if (restoreMode && !codeRequested) {
        const path = '/auth/restore/otp/'
        await api.post(path, {
          phone: normalizePhone(values.phone),
          password: values.password,
        })
        setCodeRequested(true)
        return
      }
      if (restoreMode && !/^\d{6}$/.test(loginCode)) {
        setFormError(t('error.codeInvalid'))
        return
      }
      const signedInUser = restoreMode
        ? await restore(normalizePhone(values.phone), values.password, loginCode)
        : await login(normalizePhone(values.phone), values.password, 'shop')
      navigate(
        signedInUser.must_change_password
          ? '/password/change'
          : roleHomes[signedInUser.role],
        { replace: true },
      )
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.login')))
    }
  })

  return (
    <AuthShell mode="shop">
      <div className="auth-heading">
        {restoreMode && <DevOtpBadge />}
        <span className="section-kicker">{t('auth.welcome')}</span>
        <h2>{t(restoreMode ? 'auth.restoreTitle' : 'auth.loginTitle')}</h2>
        <p>
          {restoreMode
            ? codeRequested
              ? t('auth.codeSent')
              : t('auth.restoreDescription')
            : t('auth.loginDescription')}
        </p>
      </div>

      {params.get('registered') && (
        <div className="notice success-notice"><span>✓</span> {t('auth.registeredNotice')}</div>
      )}
      {params.get('deleted') && (
        <div className="notice warning-notice"><span>!</span> {t('auth.deletedNotice')}</div>
      )}
      {params.get('reset') && (
        <div className="notice success-notice"><span>✓</span> {t('auth.passwordResetDone')}</div>
      )}

      <form className="auth-form" onSubmit={submit} noValidate>
        <PhoneControl control={control} error={errors.phone?.message} t={t} />
        <FormField label={t('common.password')} error={errors.password?.message}>
          <span className="input-wrap">
            <span className="input-leading" aria-hidden="true">⌑</span>
            <input
              {...register('password')}
              type="password"
              autoComplete="current-password"
              placeholder={t('common.passwordPlaceholder')}
              className="form-input"
            />
          </span>
        </FormField>
        {codeRequested && restoreMode && (
          <FormField label={t('common.smsCode')} hint={t('common.codeHint')}>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={loginCode}
              onChange={(event) => setLoginCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="••••••"
              className="form-input otp-input"
            />
          </FormField>
        )}
        {formError && <div className="form-alert" role="alert">{formError}</div>}
        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? <span className="button-spinner" /> : null}
          {isSubmitting ? t('auth.submitChecking') : restoreMode ? codeRequested ? t('auth.restore') : t('auth.sendRestoreCode') : t('auth.login')}
          {!isSubmitting && <span aria-hidden="true">→</span>}
        </button>
      </form>

      <div className="auth-extra">
        {!restoreMode && (
          <button type="button" className="text-button" onClick={() => navigate('/password/reset')}>
            {t('auth.forgotPassword')}
          </button>
        )}
        <button type="button" className="text-button" onClick={() => { setRestoreMode(!restoreMode); setCodeRequested(false); setLoginCode(''); setFormError('') }}>
          {restoreMode ? t('auth.restoreLink') : t('auth.cancelDeletionLink')}
        </button>
        {!restoreMode && (
          <div style={{ display: 'grid', gap: 6 }}>
            <p>{t('auth.noAccount')} <Link to="/register">{t('auth.registerLink')} <span>↗</span></Link></p>
            <p>
              {companyCopy.question}{' '}
              <Link to="/company/register" style={{ fontWeight: 600 }}>
                {companyCopy.link} <span>↗</span>
              </Link>
            </p>
          </div>
        )}
      </div>

      {!restoreMode && (
        <div className="staff-access-note">
          <span>⌑</span>
          {t('auth.driverAccess')}
        </div>
      )}
      <div className="mobile-story-note"><span className="eyebrow-dot" /> {t('auth.mobileNote')}</div>
    </AuthShell>
  )
}

function PasswordResetPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [codeRequested, setCodeRequested] = useState(false)
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const requestCode = async () => {
    const parsedPhone = createPhoneSchema(t).safeParse(phone)
    if (!parsedPhone.success) {
      setFormError(parsedPhone.error.issues[0]?.message ?? t('error.phoneCheck'))
      return
    }
    setFormError('')
    setIsSubmitting(true)
    try {
      await api.post('/auth/password/reset/otp/', { phone: normalizePhone(phone) })
      setCodeRequested(true)
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.request')))
    } finally {
      setIsSubmitting(false)
    }
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError('')
    if (!codeRequested) {
      await requestCode()
      return
    }
    if (!/^\d{6}$/.test(code)) {
      setFormError(t('error.codeInvalid'))
      return
    }
    if (password.length < 8) {
      setFormError(t('error.passwordTooShort'))
      return
    }
    if (password !== passwordConfirm) {
      setFormError(t('error.passwordMismatch'))
      return
    }
    setIsSubmitting(true)
    try {
      await api.post('/auth/password/reset/', {
        phone: normalizePhone(phone),
        code,
        password,
        password_confirm: passwordConfirm,
      })
      navigate('/login?reset=1', { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.request')))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="auth-heading">
        <span className="section-kicker">{t('auth.welcome')}</span>
        <h2>{t('auth.resetPasswordTitle')}</h2>
        <p>{t('auth.resetPasswordDescription')}</p>
      </div>
      <form className="auth-form" onSubmit={(event) => { void submit(event) }} noValidate>
        <FormField label={t('auth.newPhone')}>
          <input
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(event) => setPhone(formatPhoneInput(event.target.value))}
            placeholder="+998 90 123 45 67"
            className="form-input"
          />
        </FormField>
        {!codeRequested ? null : (
          <>
            <FormField label={t('common.smsCode')} hint={t('common.codeHint')}>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                className="form-input otp-input"
              />
            </FormField>
            <FormField label={t('auth.newPassword')}>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="form-input"
              />
            </FormField>
            <FormField label={t('auth.confirmNewPassword')}>
              <input
                type="password"
                autoComplete="new-password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                className="form-input"
              />
            </FormField>
          </>
        )}
        {formError && <div className="form-alert" role="alert">{formError}</div>}
        <button
          className="primary-button"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? <span className="button-spinner" /> : null}
          {isSubmitting
            ? t('auth.submitChecking')
            : codeRequested
              ? t('auth.resetPassword')
              : t('auth.sendResetCode')}
          {!isSubmitting && <span aria-hidden="true">→</span>}
        </button>
      </form>
      <div className="auth-extra">
        <Link to="/login">{t('auth.backToLogin')}</Link>
      </div>
    </AuthShell>
  )
}

function PasswordChangePage() {
  const { t } = useTranslation()
  const { changePassword, logout, user } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError('')
    if (password.length < 8) {
      setFormError(t('error.passwordTooShort'))
      return
    }
    if (password !== passwordConfirm) {
      setFormError(t('error.passwordMismatch'))
      return
    }
    setIsSubmitting(true)
    try {
      const updatedUser = await changePassword(currentPassword, password, passwordConfirm)
      navigate(roleHomes[updatedUser.role], { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.request')))
    } finally {
      setIsSubmitting(false)
    }
  }

  const signOut = async () => {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.logout')))
    }
  }

  return (
    <AuthShell mode={user?.role === 'shop_owner' ? 'shop' : 'staff'}>
      <div className="auth-heading">
        <span className="section-kicker">{t('auth.welcome')}</span>
        <h2>{t('auth.changePasswordTitle')}</h2>
        <p>{t('auth.changePasswordDescription')}</p>
      </div>
      <form className="auth-form" onSubmit={(event) => { void submit(event) }} noValidate>
        <FormField label={t('common.currentPassword')}>
          <input
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            className="form-input"
          />
        </FormField>
        <FormField label={t('auth.newPassword')}>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="form-input"
          />
        </FormField>
        <FormField label={t('auth.confirmNewPassword')}>
          <input
            type="password"
            autoComplete="new-password"
            value={passwordConfirm}
            onChange={(event) => setPasswordConfirm(event.target.value)}
            className="form-input"
          />
        </FormField>
        {formError && <div className="form-alert" role="alert">{formError}</div>}
        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? <span className="button-spinner" /> : null}
          {isSubmitting ? t('auth.submitChecking') : t('auth.changePassword')}
        </button>
      </form>
      <div className="auth-extra">
        <button type="button" className="text-button" onClick={() => void signOut()}>
          {t('nav.logout')}
        </button>
      </div>
    </AuthShell>
  )
}

function RegisterPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [step, setStep] = useState<'phone' | 'verify'>('phone')
  const [formError, setFormError] = useState('')
  const [sentPhone, setSentPhone] = useState('')
  const phoneSchema = useMemo(() => createPhoneSchema(t), [t])
  const registerSchema = useMemo(() => createRegisterSchema(t), [t])
  const { register, control, handleSubmit, formState: { errors, isSubmitting }, getValues } =
    useForm<RegisterValues>({
      resolver: zodResolver(registerSchema),
      defaultValues: { phone: '', code: '', password: '' },
    })

  const sendCode = async () => {
    const phone = getValues('phone')
    const parsed = phoneSchema.safeParse(phone)
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? t('error.phoneCheck'))
      return
    }
    setFormError('')
    try {
      await api.post('/auth/register/otp/', { phone: normalizePhone(phone) })
      setSentPhone(normalizePhone(phone))
      setStep('verify')
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.registerSms')))
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
      setFormError(apiErrorMessage(error, t('error.register')))
    }
  })

  return (
    <AuthShell>
      <div className="auth-heading">
        <DevOtpBadge />
        <span className="section-kicker">{t('register.eyebrow')}</span>
        <h2>{t('register.title')}</h2>
        <p>{t('register.description')}</p>
      </div>
      <div className="step-indicator">
        <span className="step-number active-step">1</span><i className={step === 'verify' ? 'step-line complete-line' : 'step-line'} />
        <span className={`step-number ${step === 'verify' ? 'active-step' : ''}`}>2</span>
        <span className="step-label">{t(step === 'phone' ? 'register.stepPhone' : 'register.stepVerify')}</span>
      </div>

      <form className="auth-form register-form" onSubmit={step === 'verify' ? submit : (event) => { event.preventDefault(); void sendCode() }} noValidate>
        <FormField label={t('common.phone')} error={errors.phone?.message} hint={t('register.phoneHint')}>
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
            <FormField
              label={t('common.smsCode')}
              error={errors.code?.message}
              hint={t('register.codeHint').replace('{phone}', sentPhone)}
            >
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
            <FormField label={t('register.password')} error={errors.password?.message} hint={t('register.passwordHint')}>
              <input
                {...register('password')}
                type="password"
                autoComplete="new-password"
                placeholder={t('register.passwordPlaceholder')}
                className="form-input"
              />
            </FormField>
          </>
        )}
        {formError && <div className="form-alert" role="alert">{formError}</div>}
        <button className="primary-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? <span className="button-spinner" /> : null}
          {isSubmitting ? t('common.checking') : step === 'phone' ? t('auth.sendCode') : t('register.submit')}
          {!isSubmitting && <span aria-hidden="true">→</span>}
        </button>
        {step === 'verify' && (
          <button type="button" className="text-button centered-button" onClick={() => { setStep('phone'); setFormError('') }}>
            {t('register.changePhone')}
          </button>
        )}
      </form>
      <div className="auth-extra">
        <p>{t('register.hasAccount')} <Link to="/login">{t('register.loginLink')} <span>↗</span></Link></p>
      </div>
    </AuthShell>
  )
}

function ProfilePage() {
  const { language, t } = useTranslation()
  const { user, completeDeletion, changePhone } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState('')
  const [deletionCode, setDeletionCode] = useState('')
  const [deletionCodeRequested, setDeletionCodeRequested] = useState(false)
  const [deletionCodeSending, setDeletionCodeSending] = useState(false)
  const [newPhone, setNewPhone] = useState('')
  const [phoneCode, setPhoneCode] = useState('')
  const [phoneCodeRequested, setPhoneCodeRequested] = useState(false)
  const [phoneCodeSending, setPhoneCodeSending] = useState(false)
  const [phoneError, setPhoneError] = useState('')
  const [phoneMessage, setPhoneMessage] = useState('')
  const deletionSchema = useMemo(() => createDeletionSchema(t), [t])
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
    if (!/^\d{6}$/.test(deletionCode)) {
      setFormError(t('error.codeInvalid'))
      return
    }
    try {
      await api.post('/auth/me/deletion/', { ...values, code: deletionCode })
      await queryClient.invalidateQueries({ queryKey: ['account-deletion'] })
      completeDeletion()
      navigate('/login?deleted=1', { replace: true })
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.deletion')))
    }
  })

  const sendDeletionCode = async () => {
    setFormError('')
    setDeletionCodeSending(true)
    try {
      await api.post('/auth/me/deletion/otp/')
      setDeletionCodeRequested(true)
    } catch (error) {
      setFormError(apiErrorMessage(error, t('error.request')))
    } finally {
      setDeletionCodeSending(false)
    }
  }

  const sendPhoneCode = async () => {
    const parsedPhone = createPhoneSchema(t).safeParse(newPhone)
    if (!parsedPhone.success) {
      setPhoneError(parsedPhone.error.issues[0]?.message ?? t('error.phoneCheck'))
      return
    }
    setPhoneError('')
    setPhoneMessage('')
    setPhoneCodeSending(true)
    try {
      await api.post('/auth/phone/change/otp/', { phone: normalizePhone(newPhone) })
      setPhoneCodeRequested(true)
    } catch (error) {
      setPhoneError(apiErrorMessage(error, t('error.request')))
    } finally {
      setPhoneCodeSending(false)
    }
  }

  const submitPhoneChange = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPhoneError('')
    if (!/^\d{6}$/.test(phoneCode)) {
      setPhoneError(t('error.codeInvalid'))
      return
    }
    try {
      await changePhone(normalizePhone(newPhone), phoneCode)
      setNewPhone('')
      setPhoneCode('')
      setPhoneCodeRequested(false)
      setPhoneMessage(t('profile.phoneUpdated'))
    } catch (error) {
      setPhoneError(apiErrorMessage(error, t('error.request')))
    }
  }

  return (
    <DashboardShell active="profile">
      <div className="page-title-row">
        <div>
          <span className="section-kicker">{t('profile.settings')}</span>
          <h1>{t('profile.title')}</h1>
          <p>{t('profile.description')}</p>
        </div>
        <span className="profile-avatar">{user?.phone.slice(-2)}</span>
      </div>

      <section className="profile-card">
        <div className="card-title-row">
          <div className="card-icon">◎</div>
          <div><h2>{t('profile.personalData')}</h2><p>{t('profile.linkedData')}</p></div>
        </div>
        <dl className="profile-details">
          <div><dt>{t('profile.phone')}</dt><dd>{user?.phone}</dd></div>
          <div><dt>{t('profile.userType')}</dt><dd><span className="role-pill">{user ? t(roleLabelKeys[user.role]) : ''}</span></dd></div>
          <div><dt>{t('profile.company')}</dt><dd>{user?.company_id ? `${t('profile.company')} #${user.company_id}` : t('profile.independentShop')}</dd></div>
        </dl>
      </section>

      <section className="profile-card">
        <div className="card-title-row">
          <div className="card-icon">⌕</div>
          <div><h2>{t('auth.phoneChangeTitle')}</h2><p>{t('auth.phoneChangeDescription')}</p></div>
        </div>
        <form className="deletion-form" onSubmit={(event) => void submitPhoneChange(event)} noValidate>
          <FormField label={t('auth.newPhone')}>
            <input
              type="tel"
              autoComplete="tel"
              value={newPhone}
              onChange={(event) => setNewPhone(formatPhoneInput(event.target.value))}
              placeholder="+998 90 123 45 67"
              className="form-input"
            />
          </FormField>
          {phoneCodeRequested && (
            <FormField label={t('common.smsCode')} hint={t('common.codeHint')}>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={phoneCode}
                onChange={(event) => setPhoneCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                className="form-input otp-input"
              />
            </FormField>
          )}
          {phoneError && <div className="form-alert" role="alert">{phoneError}</div>}
          {phoneMessage && <div className="notice success-notice" role="status">{phoneMessage}</div>}
          <div className="deletion-actions">
            {!phoneCodeRequested ? (
              <button
                className="primary-button"
                disabled={phoneCodeSending}
                type="button"
                onClick={() => void sendPhoneCode()}
              >
                {phoneCodeSending ? t('auth.submitChecking') : t('auth.sendPhoneCode')}
              </button>
            ) : (
              <button className="primary-button" type="submit">{t('auth.changePhone')}</button>
            )}
          </div>
        </form>
      </section>

      {user?.role === 'shop_owner' && (
        <section className="danger-card">
          <div className="card-title-row">
            <div className="card-icon danger-icon">!</div>
            <div><h2>{t('profile.deleteAccount')}</h2><p>{t('profile.deletePendingHint')}</p></div>
          </div>
          {deletion.isLoading ? (
            <div className="loading-row"><span className="button-spinner" /> {t('profile.checkingStatus')}</div>
          ) : deletion.data?.pending ? (
            <div className="pending-deletion">
              <span className="pending-icon">◷</span>
              <div>
                <strong>{t('profile.deletionPending')}</strong>
                <p>
                  {t('profile.anonymizedOn').replace(
                    '{date}',
                    deletion.data.scheduled_for
                      ? formatDate(deletion.data.scheduled_for, language)
                      : t('profile.daysRemaining'),
                  )}
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="deletion-warning">
                <strong>{t('profile.beforeContinue')}</strong>
                <p>{t('profile.closeOrdersAndDebt')}</p>
              </div>
              <form className="deletion-form" onSubmit={submit} noValidate>
                <FormField label={t('profile.deletionReason')} error={errors.reason?.message}>
                  <select {...register('reason')} className="form-input select-input">
                    <option value="store_closed">{t('profile.reasonStoreClosed')}</option>
                    <option value="moved">{t('profile.reasonMoved')}</option>
                    <option value="not_needed">{t('profile.reasonNotNeeded')}</option>
                    <option value="other">{t('profile.reasonOther')}</option>
                  </select>
                </FormField>
                {reason === 'other' && (
                  <FormField label={t('profile.reasonOther')} error={errors.reason_other?.message}>
                    <textarea {...register('reason_other')} className="form-input textarea-input" rows={3} placeholder={t('profile.reasonPlaceholder')} />
                  </FormField>
                )}
                <FormField label={t('common.confirmPassword')} error={errors.password?.message}>
                  <input {...register('password')} type="password" autoComplete="current-password" className="form-input" placeholder={t('common.currentPassword')} />
                </FormField>
                {deletionCodeRequested && (
                  <FormField label={t('auth.deletionCode')} hint={t('common.codeHint')}>
                    <input
                      type="text"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      value={deletionCode}
                      onChange={(event) => setDeletionCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                      className="form-input otp-input"
                    />
                  </FormField>
                )}
                {formError && <div className="form-alert" role="alert">{formError}</div>}
                <div className="deletion-actions">
                  {!deletionCodeRequested ? (
                    <button className="primary-button" disabled={deletionCodeSending} type="button" onClick={() => void sendDeletionCode()}>
                      {deletionCodeSending ? <span className="button-spinner" /> : null} {t('auth.sendDeletionCode')}
                    </button>
                  ) : (
                    <button className="danger-button" disabled={isSubmitting} type="submit">
                      {isSubmitting ? <span className="button-spinner" /> : null} {t('profile.submitDeletion')}
                    </button>
                  )}
                  <span>{t('profile.restoreWithinDays')}</span>
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
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [logoutError, setLogoutError] = useState('')
  const signOut = async () => {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      setLogoutError(t('error.logout'))
    }
  }

  return (
    <main className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <Brand />
        <div className="sidebar-divider" />
        <span className="sidebar-label">{t('nav.personalCabinet')}</span>
        <nav className="sidebar-nav">
          <Link to={user ? roleHomes[user.role] : '/login'} className="sidebar-link">
            <span>▦</span> {t('nav.home')}
          </Link>
          <Link to="/profile" className={`sidebar-link ${active === 'profile' ? 'sidebar-active' : ''}`}>
            <span>◎</span> {t('nav.profileSecurity')}
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-user">
            <span className="profile-avatar small-avatar">{user?.phone.slice(-2)}</span>
            <span><strong>{user?.phone}</strong><small>{user ? t(roleLabelKeys[user.role]) : ''}</small></span>
          </div>
          {logoutError && <p className="sidebar-error">{logoutError}</p>}
          <button type="button" className="logout-button" onClick={() => void signOut()}>
            <span>↪</span> {t('nav.logout')}
          </button>
        </div>
      </aside>
      <section className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="breadcrumb">{t('nav.breadcrumb')} <span>/</span> {t('nav.profileSecurity')}</div>
          <div className="auth-controls"><LanguageSelect /><ThemeToggle /></div>
        </header>
        <div className="dashboard-content">{children}</div>
      </section>
    </main>
  )
}

function RoleLandingPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  if (!user) return null
  return (
    <DashboardShell active="home">
      <div className="empty-panel">
        <span className="empty-panel-mark">✳</span>
        <span className="section-kicker">{t('landing.eyebrow')}</span>
        <h1>{t(roleLabelKeys[user.role])}</h1>
        <p>{t('landing.description')}</p>
        <Link className="secondary-button" to="/profile">{t('nav.profileSecurity')} <span>→</span></Link>
      </div>
    </DashboardShell>
  )
}

function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <main className="full-loader"><span className="button-spinner" /> {t('loading.secure')}</main>
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (user.must_change_password && location.pathname !== '/password/change') {
    return <Navigate to="/password/change" replace />
  }
  if (!user.must_change_password && location.pathname === '/password/change') {
    return <Navigate to={roleHomes[user.role]} replace />
  }
  if (!canAccessRoles(user.role, roles)) {
    return <Navigate to={roleHomes[user.role]} replace />
  }
  return children
}

function IndexRedirect() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  if (loading) return <main className="full-loader"><span className="button-spinner" /> {t('common.loading')}</main>
  return (
    <Navigate
      to={user
        ? user.must_change_password
          ? '/password/change'
          : roleHomes[user.role]
        : '/login'}
      replace
    />
  )
}

function App() {
  const { t } = useTranslation()
  return (
    <Routes>
      <Route path="/" element={<Suspense fallback={<main className="full-loader">{t('common.loading')}</main>}><LandingChoicePage /></Suspense>} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/staff/login" element={<Navigate to="/login" replace />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/company/register" element={<Suspense fallback={<main className="full-loader">{t('common.loading')}</main>}><CompanyRegisterPage /></Suspense>} />
      <Route path="/password/reset" element={<PasswordResetPage />} />
      <Route path="/password/change" element={<ProtectedRoute><PasswordChangePage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute roles={['super_admin']}><RoleLandingPage /></ProtectedRoute>} />
      <Route path="/directory/companies" element={<ProtectedRoute roles={['shop_owner']}><Navigate to="/shop/directory" replace /></ProtectedRoute>} />
      <Route path="/my/companies" element={<ProtectedRoute roles={['shop_owner']}><Navigate to="/shop/my-companies" replace /></ProtectedRoute>} />
      <Route path="/company/*" element={<ProtectedRoute roles={['company_admin']}><Suspense fallback={<main className="full-loader">{t('common.loading')}</main>}><DispatcherPanel /></Suspense></ProtectedRoute>} />
      <Route path="/driver/*" element={<ProtectedRoute roles={['driver']}><Suspense fallback={<main className="full-loader">{t('common.loading')}</main>}><DriverPanel /></Suspense></ProtectedRoute>} />
      <Route path="/shop/*" element={<ProtectedRoute roles={['shop_owner']}><Suspense fallback={<main className="full-loader">{t('common.loading')}</main>}><ShopPanel /></Suspense></ProtectedRoute>} />
      <Route path="*" element={<IndexRedirect />} />
    </Routes>
  )
}

export default App
