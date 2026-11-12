import { ArrowLeft, ArrowRight, Building2, Check, CheckCircle2, UserCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import api, { apiErrorMessage } from './api'
import './App.css'

const DISTRICT_OPTIONS = [
  'Guliston',
  'Yangiyer',
  'Shirin',
  'Boyovut',
  'Sayxunobod',
  'Mirzaobod',
  'Oqoltin',
  'Sardoba',
  'Xovos',
  'Sirdaryo',
]

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

export default function CompanyRegisterPage() {
  const [step, setStep] = useState<1 | 2>(1)

  // Step 1: Company details
  const [name, setName] = useState('')
  const [taxId, setTaxId] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [description, setDescription] = useState('')
  const [districts, setDistricts] = useState<string[]>(['Guliston'])

  // Step 2: Admin credentials & OTP
  const [adminPhone, setAdminPhone] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [otpRequested, setOtpRequested] = useState(false)
  const [otpSending, setOtpSending] = useState(false)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)

  const toggleDistrict = (d: string) => {
    if (districts.includes(d)) {
      if (districts.length > 1) {
        setDistricts(districts.filter((item) => item !== d))
      }
    } else {
      setDistricts([...districts, d])
    }
  }

  const handleStep1Next = (e: FormEvent) => {
    e.preventDefault()
    setFormError('')
    if (!name.trim()) {
      setFormError('Kompaniya nomini kiriting.')
      return
    }
    const rawContact = contactPhone.replace(/\D/g, '').replace(/^998/, '')
    if (rawContact.length !== 9) {
      setFormError('Aloqa telefon raqamini to‘liq kiriting (+998 XX XXX XX XX).')
      return
    }
    setStep(2)
  }

  const handleSendOtp = async () => {
    setFormError('')
    const rawAdmin = adminPhone.replace(/\D/g, '').replace(/^998/, '')
    if (rawAdmin.length !== 9) {
      setFormError('Administrator telefon raqamini to‘liq kiriting.')
      return
    }
    setOtpSending(true)
    try {
      await api.post('/auth/register/otp/', { phone: normalizePhone(adminPhone) })
      setOtpRequested(true)
    } catch (err) {
      setFormError(apiErrorMessage(err, 'SMS kod yuborishda xatolik yuz berdi.'))
    } finally {
      setOtpSending(false)
    }
  }

  const handleFinalSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setFormError('')

    const rawAdmin = adminPhone.replace(/\D/g, '').replace(/^998/, '')
    if (rawAdmin.length !== 9) {
      setFormError('Administrator telefon raqamini to‘liq kiriting.')
      return
    }
    if (!/^\d{6}$/.test(otpCode.trim())) {
      setFormError('6 xonali SMS tasdiqlash kodini kiriting.')
      return
    }
    if (password.length < 8) {
      setFormError('Parol kamida 8 ta belgidan iborat bo‘lishi kerak.')
      return
    }
    if (password !== confirmPassword) {
      setFormError('Kiritilgan parollar bir-biriga mos kelmadi.')
      return
    }

    setIsSubmitting(true)
    try {
      await api.post('/v1/companies/register/', {
        name: name.trim(),
        tax_id: taxId.trim(),
        description: description.trim(),
        contact_phone: normalizePhone(contactPhone),
        service_districts: districts,
        admin_phone: normalizePhone(adminPhone),
        code: otpCode.trim(),
        password,
      })
      setIsSuccess(true)
    } catch (err) {
      setFormError(apiErrorMessage(err, 'Kompaniyani ro‘yxatdan o‘tkazib bo‘lmadi. Ma’lumotlarni tekshiring.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSuccess) {
    return (
      <main className="auth-layout">
        <div className="auth-card" style={{ maxWidth: 520, textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', padding: 14, background: 'rgba(34,197,94,0.15)', borderRadius: '50%', color: '#22c55e', marginBottom: '1rem' }}>
            <CheckCircle2 size={44} />
          </div>
          <h1 style={{ fontSize: '1.4rem', marginBottom: '0.5rem' }}>Arizangiz muvaffaqiyatli qabul qilindi!</h1>
          <p style={{ color: 'var(--muted)', fontSize: '0.95rem', lineHeight: 1.5, marginBottom: '1.5rem' }}>
            <strong>{name}</strong> kompaniyasi ro‘yxatga olindi va super admin tasdiqlashi uchun yuborildi.
            <br />
            Tasdiqlangunga qadar kompaniya kabinetiga kirib, mahsulot va narxlarni kiritishni boshlashingiz mumkin.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <Link to="/staff/login" className="primary-button" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8 }}>
              <span>Kompaniya kabinetiga kirish</span> <ArrowRight size={16} />
            </Link>
            <Link to="/" className="text-link" style={{ textAlign: 'center', marginTop: 8 }}>
              Bosh sahifaga qaytish
            </Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="auth-layout">
      <div className="auth-card" style={{ maxWidth: 560 }}>
        <div className="auth-header" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', color: 'var(--accent)' }}>
            <Building2 size={24} />
            <span style={{ fontWeight: 700, fontSize: '1.1rem', letterSpacing: '0.04em' }}>TARQATUV PLATFORMASI</span>
          </div>
          <h1 style={{ fontSize: '1.35rem', marginTop: '0.5rem' }}>Yangi kompaniya ro‘yxatdan o‘tkazish</h1>
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
            {step === 1 ? '1-bosqich: Kompaniya ma’lumotlari' : '2-bosqich: Administrator akkaunti va tasdiqlash'}
          </p>
        </div>

        {/* Stepper indicator */}
        <div style={{ display: 'flex', gap: 8, marginBottom: '1.5rem' }}>
          <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'var(--accent)' }} />
          <div style={{ flex: 1, height: 4, borderRadius: 2, background: step === 2 ? 'var(--accent)' : 'var(--border)' }} />
        </div>

        {formError && (
          <div className="form-alert" role="alert" style={{ marginBottom: '1.25rem' }}>
            {formError}
          </div>
        )}

        {step === 1 ? (
          <form onSubmit={handleStep1Next} noValidate>
            <div className="form-field">
              <label>Kompaniya / Distribyutor nomi *</label>
              <input
                type="text"
                required
                autoFocus
                placeholder="Masalan: Sirdaryo Savdo MCHJ"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="form-input"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-field">
                <label>Ommaviy aloqa telefoni *</label>
                <input
                  type="tel"
                  required
                  placeholder="+998 90 123 45 67"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(formatPhoneInput(e.target.value))}
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label>STIR / Soliq ID (ixtiyoriy)</label>
                <input
                  type="text"
                  placeholder="Masalan: 123456789"
                  value={taxId}
                  onChange={(e) => setTaxId(e.target.value)}
                  className="form-input"
                />
              </div>
            </div>

            <div className="form-field">
              <label>Xizmat ko‘rsatish tumanlari</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                {DISTRICT_OPTIONS.map((d) => {
                  const sel = districts.includes(d)
                  return (
                    <button
                      key={d}
                      type="button"
                      onClick={() => toggleDistrict(d)}
                      style={{
                        padding: '5px 10px',
                        borderRadius: 20,
                        border: '1px solid',
                        borderColor: sel ? 'var(--accent)' : 'var(--border)',
                        background: sel ? 'var(--accent)' : 'transparent',
                        color: sel ? '#fff' : 'inherit',
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {sel && <Check size={12} />} {d}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="form-field">
              <label>Kompaniya haqida qisqacha tavsif (ixtiyoriy)</label>
              <textarea
                rows={2}
                placeholder="Yetkazib beriladigan mahsulotlar toifasi, shartlar…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="form-input"
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem' }}>
              <Link to="/staff/login" className="text-link" style={{ fontSize: '0.88rem' }}>
                Akkauntingiz bormi? Kirish
              </Link>
              <button type="submit" className="primary-button" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>Davom etish</span> <ArrowRight size={16} />
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleFinalSubmit} noValidate>
            <div className="form-field">
              <label>Administrator telefon raqami *</label>
              <input
                type="tel"
                required
                autoFocus
                placeholder="+998 90 123 45 67"
                value={adminPhone}
                onChange={(e) => setAdminPhone(formatPhoneInput(e.target.value))}
                className="form-input"
              />
            </div>

            <div className="form-field">
              <label>SMS tasdiqlash kodi *</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="text"
                  required
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="form-input otp-input"
                  style={{ letterSpacing: '0.2em', fontWeight: 700 }}
                />
                <button
                  type="button"
                  className="secondary-button"
                  disabled={otpSending}
                  onClick={handleSendOtp}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {otpSending ? 'Yuborilmoqda…' : otpRequested ? 'Qayta yuborish' : 'Kodni olish'}
                </button>
              </div>
              <small style={{ color: 'var(--muted)', fontSize: '0.8rem', marginTop: 4, display: 'block' }}>
                Mahalliy rejimda dev OTP kodi: <strong>123456</strong>
              </small>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-field">
                <label>Kirish paroli *</label>
                <input
                  type="password"
                  required
                  placeholder="Kamida 8 belgi"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label>Parolni tasdiqlang *</label>
                <input
                  type="password"
                  required
                  placeholder="Qayta kiriting"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="form-input"
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem' }}>
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  setStep(1)
                  setFormError('')
                }}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <ArrowLeft size={16} /> <span>Ortga</span>
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={isSubmitting}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {isSubmitting ? (
                  <>
                    <span className="button-spinner" /> <span>Tekshirilmoqda…</span>
                  </>
                ) : (
                  <>
                    <UserCheck size={16} /> <span>Ro‘yxatdan o‘tish</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  )
}
