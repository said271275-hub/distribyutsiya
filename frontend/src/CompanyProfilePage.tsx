import { Building2, Check, CheckCircle2, Clock, Image as ImageIcon, Phone, Save, ShieldAlert, Sparkles, XCircle } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import './DispatcherPanel.css'

export type CompanyMe = {
  id: number
  name: string
  slug: string
  status: 'pending' | 'active' | 'suspended' | 'rejected'
  rejection_reason: string
  description: string
  tax_id: string
  service_districts: string[]
  contact_phone: string
  brand_color: string
  auto_approve_subscriptions: boolean
  logo: string | null
  created_at: string
}

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

export default function CompanyProfilePage() {
  const queryClient = useQueryClient()
  const [successMessage, setSuccessMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)

  const companyQuery = useQuery({
    queryKey: ['company-me'],
    queryFn: async () => (await api.get<CompanyMe>('/v1/company/me/')).data,
  })

  const [description, setDescription] = useState<string | null>(null)
  const [contactPhone, setContactPhone] = useState<string | null>(null)
  const [autoApprove, setAutoApprove] = useState<boolean | null>(null)
  const [selectedDistricts, setSelectedDistricts] = useState<string[] | null>(null)

  const data = companyQuery.data

  const currentDescription = description !== null ? description : (data?.description ?? '')
  const currentContactPhone = contactPhone !== null ? contactPhone : (data?.contact_phone ?? '')
  const currentAutoApprove = autoApprove !== null ? autoApprove : (data?.auto_approve_subscriptions ?? false)
  const currentDistricts = selectedDistricts !== null ? selectedDistricts : (data?.service_districts ?? [])

  const updateMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData()
      formData.append('description', currentDescription)
      formData.append('contact_phone', currentContactPhone)
      formData.append('auto_approve_subscriptions', String(currentAutoApprove))
      formData.append('service_districts', JSON.stringify(currentDistricts))
      if (logoFile) {
        formData.append('logo', logoFile)
      }
      return (await api.patch<CompanyMe>('/v1/company/me/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })).data
    },
    onSuccess: (updated) => {
      setSuccessMessage('Kompaniya profili muvaffaqiyatli saqlandi.')
      setErrorMessage('')
      setLogoFile(null)
      queryClient.setQueryData(['company-me'], updated)
      setTimeout(() => setSuccessMessage(''), 4000)
    },
    onError: (error) => {
      setErrorMessage(apiErrorMessage(error, 'Kompaniya ma’lumotlarini saqlab bo‘lmadi.'))
      setSuccessMessage('')
    },
  })

  const handleLogoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (file.size > 2 * 1024 * 1024) {
      setErrorMessage('Logotip hajmi 2 MB dan oshmasligi kerak.')
      return
    }
    setLogoFile(file)
    setLogoPreview(URL.createObjectURL(file))
    setErrorMessage('')
  }

  const toggleDistrict = (district: string) => {
    if (currentDistricts.includes(district)) {
      setSelectedDistricts(currentDistricts.filter((d) => d !== district))
    } else {
      setSelectedDistricts([...currentDistricts, district])
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')
    updateMutation.mutate()
  }

  if (companyQuery.isLoading) {
    return <div className="dispatcher-loading" role="status">Kompaniya ma’lumotlari yuklanmoqda…</div>
  }

  if (companyQuery.isError || !data) {
    return (
      <div className="dispatcher-error-state" role="alert">
        <p>{apiErrorMessage(companyQuery.error, 'Kompaniya ma’lumotlarini yuklab bo‘lmadi.')}</p>
        <button type="button" onClick={() => void companyQuery.refetch()}>Qayta urinish</button>
      </div>
    )
  }

  const statusBadges: Record<string, { label: string; tone: string; icon: typeof CheckCircle2 }> = {
    active: { label: 'Faol tasdiqlangan', tone: 'dispatcher-badge-green', icon: CheckCircle2 },
    pending: { label: 'Tasdiqlash kutilmoqda', tone: 'dispatcher-badge-amber', icon: Clock },
    suspended: { label: 'To‘xtatilgan', tone: 'dispatcher-badge-red', icon: ShieldAlert },
    rejected: { label: 'Rad etilgan', tone: 'dispatcher-badge-red', icon: XCircle },
  }
  const badge = statusBadges[data.status] ?? statusBadges.pending
  const BadgeIcon = badge.icon

  return (
    <div className="dispatcher-profile-page">
      <div className="dispatcher-section-heading">
        <div>
          <span className="dispatcher-eyebrow">SOZLAMALAR</span>
          <h2>Kompaniya profili</h2>
          <p>Kompaniya ma’lumotlari, logotipi va xizmat ko‘rsatish hududlarini boshqaring.</p>
        </div>
      </div>

      {successMessage && (
        <div className="dispatcher-alert dispatcher-alert-success" role="status">
          <Check size={18} /> <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="dispatcher-alert dispatcher-alert-error" role="alert">
          <XCircle size={18} /> <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="dispatcher-profile-form">
        <div className="dispatcher-card dispatcher-profile-card">
          <div className="dispatcher-card-header">
            <Building2 size={20} />
            <h3>Asosiy ma’lumotlar</h3>
          </div>

          <div className="dispatcher-form-grid">
            <div className="dispatcher-field">
              <label>Kompaniya nomi (o‘zgarmas)</label>
              <input type="text" value={data.name} disabled className="dispatcher-input dispatcher-input-disabled" />
            </div>

            <div className="dispatcher-field">
              <label>Identifikator (Slug)</label>
              <input type="text" value={data.slug} disabled className="dispatcher-input dispatcher-input-disabled" />
            </div>

            <div className="dispatcher-field">
              <label>STIR / Soliq raqami (STIR)</label>
              <input type="text" value={data.tax_id || 'Mavjud emas'} disabled className="dispatcher-input dispatcher-input-disabled" />
            </div>

            <div className="dispatcher-field">
              <label>Holati</label>
              <div className={`dispatcher-status-badge ${badge.tone}`}>
                <BadgeIcon size={15} /> <span>{badge.label}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="dispatcher-card dispatcher-profile-card">
          <div className="dispatcher-card-header">
            <ImageIcon size={20} />
            <h3>Logotip va aloqa</h3>
          </div>

          <div className="dispatcher-logo-row">
            <div className="dispatcher-logo-preview">
              {logoPreview || data.logo ? (
                <img src={logoPreview || data.logo || ''} alt={`${data.name} logotipi`} />
              ) : (
                <div className="dispatcher-logo-placeholder">
                  <Building2 size={36} />
                  <span>Logotip yo‘q</span>
                </div>
              )}
            </div>
            <div className="dispatcher-logo-controls">
              <label className="dispatcher-file-upload-btn">
                <span>Rasm tanlash (PNG, JPG, WebP)</span>
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={handleLogoChange} />
              </label>
              <small>Maksimal hajm: 2 MB. Tavsiya etilgan o‘lcham: kvadrat (masalan 400x400).</small>
            </div>
          </div>

          <div className="dispatcher-form-grid" style={{ marginTop: '1rem' }}>
            <div className="dispatcher-field">
              <label htmlFor="company-phone">Ommaviy aloqa telefoni</label>
              <div className="dispatcher-input-icon-wrap">
                <Phone size={16} />
                <input
                  id="company-phone"
                  type="tel"
                  required
                  placeholder="+998 90 123 45 67"
                  value={currentContactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  className="dispatcher-input"
                />
              </div>
            </div>

            <div className="dispatcher-field" style={{ gridColumn: '1 / -1' }}>
              <label htmlFor="company-desc">Kompaniya haqida tavsif</label>
              <textarea
                id="company-desc"
                rows={3}
                placeholder="Do‘konlarga ko‘rinadigan tavsif, yetkazib berish shartlari…"
                value={currentDescription}
                onChange={(e) => setDescription(e.target.value)}
                className="dispatcher-input"
              />
            </div>
          </div>
        </div>

        <div className="dispatcher-card dispatcher-profile-card">
          <div className="dispatcher-card-header">
            <Sparkles size={20} />
            <h3>Xizmat ko‘rsatish sozlamalari</h3>
          </div>

          <div className="dispatcher-field">
            <label>Xizmat ko‘rsatiladigan tumanlar</label>
            <p className="dispatcher-field-hint">Quyidagi tumanlardagi do‘konlar sizga buyurtma bera oladi:</p>
            <div className="dispatcher-district-chips">
              {DISTRICT_OPTIONS.map((district) => {
                const selected = currentDistricts.includes(district)
                return (
                  <button
                    key={district}
                    type="button"
                    onClick={() => toggleDistrict(district)}
                    className={`dispatcher-chip ${selected ? 'dispatcher-chip-selected' : ''}`}
                  >
                    {selected && <Check size={14} />} {district}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="dispatcher-toggle-row">
            <div>
              <strong>Do‘konlar obunasini avtomatik tasdiqlash</strong>
              <p>Yoqilganda, do‘kon obuna so‘ragan zahoti kutmasdan faollashtiriladi.</p>
            </div>
            <label className="dispatcher-switch">
              <input
                type="checkbox"
                checked={currentAutoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
              />
              <span className="dispatcher-slider" />
            </label>
          </div>
        </div>

        <div className="dispatcher-form-actions">
          <button
            type="submit"
            className="dispatcher-primary-btn"
            disabled={updateMutation.isPending}
          >
            <Save size={17} />
            <span>{updateMutation.isPending ? 'Saqlanmoqda…' : 'O‘zgarishlarni saqlash'}</span>
          </button>
        </div>
      </form>
    </div>
  )
}
