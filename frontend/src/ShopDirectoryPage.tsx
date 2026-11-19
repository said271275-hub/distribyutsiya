import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Building2,
  Search,
  Phone,
  Clock,
  CheckCircle2,
  ShieldAlert,
  ArrowRight,
  X,
  AlertTriangle,
} from 'lucide-react'
import api, { apiErrorMessage, formatMediaUrl } from './api'

export interface DirectoryCompany {
  id: number
  name: string
  contact_phone: string
  description: string
  logo: string | null
  service_districts: string[]
  order_cutoff_time: string
  subscription_status: 'none' | 'pending' | 'active' | 'rejected' | 'blocked'
  subscription_id: number | null
}

interface Page<T> {
  results: T[]
  count: number
  next?: string | null
  previous?: string | null
}

const TASHKENT_DISTRICTS = [
  'Barcha tumanlar',
  'Bektemir',
  'Chilonzor',
  'Mirobod',
  'Mirzo Ulug‘bek',
  'Olmazor',
  'Sergeli',
  'Shayxontohur',
  'Uchtepa',
  'Yakkasaroy',
  'Yangi Hayot',
  'Yashnobod',
  'Yunusobod',
]

function DirectoryCompanyLogo({ src, name }: { src: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  const resolved = formatMediaUrl(src)
  if (!resolved || failed) {
    return <Building2 size={26} strokeWidth={1.5} />
  }
  return <img src={resolved} alt={name} onError={() => setFailed(true)} loading="lazy" />
}

export default function ShopDirectoryPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [district, setDistrict] = useState('')
  const [page, setPage] = useState(1)
  const [cancelModalCompany, setCancelModalCompany] = useState<DirectoryCompany | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const queryClient = useQueryClient()

  const { data, isLoading, isError, refetch } = useQuery<Page<DirectoryCompany>>({
    queryKey: ['shop-directory', searchTerm, district, page],
    queryFn: async () => {
      const params: Record<string, string | number> = { page }
      if (searchTerm.trim()) params.q = searchTerm.trim()
      if (district && district !== 'Barcha tumanlar') params.district = district
      const res = await api.get<Page<DirectoryCompany>>('/v1/directory/companies/', { params })
      return res.data
    },
  })

  const subscribeMutation = useMutation({
    mutationFn: async (companyId: number) => {
      const res = await api.post(`/v1/directory/companies/${companyId}/subscribe/`)
      return res.data
    },
    onSuccess: (data: { detail?: string; status?: string }) => {
      setActionSuccess(data.detail || 'Obuna so‘rovi muvaffaqiyatli yuborildi!')
      setActionError(null)
      void queryClient.invalidateQueries({ queryKey: ['shop-directory'] })
      void queryClient.invalidateQueries({ queryKey: ['shop-companies'] })
      void queryClient.invalidateQueries({ queryKey: ['my-companies'] })
    },
    onError: (err) => {
      setActionError(apiErrorMessage(err, 'Obuna bo‘lishda xatolik yuz berdi'))
      setActionSuccess(null)
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async (companyId: number) => {
      const res = await api.delete(`/v1/directory/companies/${companyId}/subscribe/`)
      return res.data
    },
    onSuccess: (data: { detail?: string }) => {
      setActionSuccess(data.detail || 'Obuna bekor qilindi.')
      setActionError(null)
      setCancelModalCompany(null)
      void queryClient.invalidateQueries({ queryKey: ['shop-directory'] })
      void queryClient.invalidateQueries({ queryKey: ['shop-companies'] })
      void queryClient.invalidateQueries({ queryKey: ['my-companies'] })
    },
    onError: (err) => {
      setActionError(apiErrorMessage(err, 'Obunani bekor qilishda xatolik'))
      setCancelModalCompany(null)
    },
  })

  const companies = data?.results ?? []

  return (
    <div className="shop-directory-container">
      <div className="shop-page-heading">
        <div>
          <span className="shop-eyebrow">HAMKORLIK</span>
          <h1>Distribyutor kompaniyalar</h1>
          <p>
            O‘zingizga qulay distribyutorlarni toping, shartlari bilan tanishing va buyurtma berish uchun obuna bo‘ling.
          </p>
        </div>
        <Link to="/shop/my-companies" className="shop-secondary-button">
          Mening distribyutorlarim <ArrowRight size={15} />
        </Link>
      </div>

      {actionSuccess && (
        <div className="shop-form-success" style={{ marginBottom: 16 }}>
          <CheckCircle2 size={16} /> {actionSuccess}
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {actionError && (
        <div className="shop-form-error" style={{ marginBottom: 16 }}>
          <AlertTriangle size={16} /> {actionError}
          <button
            type="button"
            onClick={() => setActionError(null)}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      <div className="shop-catalog-toolbar">
        <label className="shop-search">
          <Search size={18} />
          <input
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value)
              setPage(1)
            }}
            placeholder="Distribyutor nomi bo‘yicha qidiruv..."
          />
        </label>

        <label className="shop-select-wrap">
          <select
            value={district}
            onChange={(e) => {
              setDistrict(e.target.value)
              setPage(1)
            }}
          >
            {TASHKENT_DISTRICTS.map((dist) => (
              <option key={dist} value={dist === 'Barcha tumanlar' ? '' : dist}>
                {dist}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <div className="shop-skeletons" aria-label="Yuklanmoqda">
          <i />
          <i />
          <i />
        </div>
      ) : isError ? (
        <div className="shop-empty-state">
          <strong>Kompaniyalar ro‘yxatini yuklab bo‘lmadi</strong>
          <button className="shop-secondary-button" type="button" onClick={() => void refetch()}>
            Qayta urinish
          </button>
        </div>
      ) : companies.length === 0 ? (
        <div className="shop-empty-state">
          <span className="shop-empty-icon">
            <Building2 size={24} />
          </span>
          <strong>Kompaniyalar topilmadi</strong>
          <p>Qidiruv shartlarini o‘zgartirib ko‘ring yoki keyinroq tashrif buyuring.</p>
        </div>
      ) : (
        <div className="shop-directory-grid">
          {companies.map((company) => {
            const status = company.subscription_status
            return (
              <article key={company.id} className="shop-directory-card">
                <div className="shop-directory-card-header">
                  <div className="shop-directory-logo">
                    <DirectoryCompanyLogo src={company.logo} name={company.name} />
                  </div>
                  <div className="shop-directory-header-meta">
                    <h3>{company.name}</h3>
                    {company.contact_phone && (
                      <a href={`tel:${company.contact_phone}`} className="shop-directory-phone">
                        <Phone size={13} /> {company.contact_phone}
                      </a>
                    )}
                  </div>
                </div>

                {company.description && (
                  <p className="shop-directory-description">{company.description}</p>
                )}

                <div className="shop-directory-details">
                  <div className="shop-directory-detail-row">
                    <span className="detail-label">
                      <Clock size={13} /> Cutoff vaqti:
                    </span>
                    <strong className="detail-value">
                      {company.order_cutoff_time.slice(0, 5)} gacha
                    </strong>
                  </div>

                  {company.service_districts && company.service_districts.length > 0 && (
                    <div className="shop-directory-districts">
                      <span className="detail-label">Xizmat hududlari:</span>
                      <div className="district-chips">
                        {company.service_districts.map((d) => (
                          <span key={d} className="district-chip">
                            {d}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="shop-directory-card-actions">
                  {status === 'active' && (
                    <div className="status-action-row">
                      <span className="subscription-badge active">
                        <CheckCircle2 size={13} /> Obuna bo‘lingan
                      </span>
                      <div className="action-buttons-group">
                        <Link
                          to={`/shop/catalog?company=${company.id}`}
                          className="shop-primary-button shop-button-sm"
                        >
                          Katalog <ArrowRight size={14} />
                        </Link>
                        <button
                          type="button"
                          className="shop-text-button-danger"
                          onClick={() => setCancelModalCompany(company)}
                        >
                          Bekor qilish
                        </button>
                      </div>
                    </div>
                  )}

                  {status === 'pending' && (
                    <div className="status-action-row">
                      <span className="subscription-badge pending">
                        <Clock size={13} /> Kutilmoqda (so‘rov yuborilgan)
                      </span>
                      <small className="status-hint">
                        Kompaniya ma’muri tasdiqlashini kuting
                      </small>
                    </div>
                  )}

                  {status === 'blocked' && (
                    <div className="status-action-row">
                      <span className="subscription-badge blocked">
                        <ShieldAlert size={13} /> Bloklangan
                      </span>
                    </div>
                  )}

                  {(status === 'none' || status === 'rejected') && (
                    <button
                      type="button"
                      className="shop-primary-button shop-wide-button"
                      disabled={subscribeMutation.isPending}
                      onClick={() => subscribeMutation.mutate(company.id)}
                    >
                      {subscribeMutation.isPending ? 'Yuborilmoqda...' : 'Obuna bo‘lish'}
                    </button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}

      {/* Cancel Confirmation Modal */}
      {cancelModalCompany && (
        <div
          className="shop-modal-backdrop"
          role="presentation"
          onClick={() => setCancelModalCompany(null)}
        >
          <section
            className="shop-confirm-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="shop-modal-close"
              type="button"
              aria-label="Yopish"
              onClick={() => setCancelModalCompany(null)}
            >
              <X size={18} />
            </button>
            <span className="shop-modal-icon" style={{ background: '#fee2e2', color: '#dc2626' }}>
              <AlertTriangle size={24} />
            </span>
            <h2>Obunani bekor qilasizmi?</h2>
            <p>
              <strong>{cancelModalCompany.name}</strong> kompaniyasiga obunani bekor qilmoqchimisiz?
              Yakunlanmagan buyurtmalar va qarzdorlik bo‘lmasligi lozim.
            </p>
            <div className="shop-modal-actions">
              <button
                type="button"
                className="shop-secondary-button"
                onClick={() => setCancelModalCompany(null)}
              >
                Ortga
              </button>
              <button
                type="button"
                className="shop-danger-button"
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate(cancelModalCompany.id)}
              >
                {cancelMutation.isPending ? 'Bekor qilinmoqda...' : 'Ha, bekor qilinsin'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
