import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Building2,
  Phone,
  Clock,
  CheckCircle2,
  ShieldAlert,
  ArrowRight,
  AlertTriangle,
  X,
  Package,
} from 'lucide-react'
import api, { apiErrorMessage } from './api'

export interface MyCompanySubscription {
  id: number
  company_id: number
  company_name: string
  company_logo: string | null
  company_phone: string
  company_order_cutoff_time: string
  status: 'pending' | 'active' | 'rejected' | 'blocked'
  is_active: boolean
  requested_at: string
  decided_at: string | null
  reject_reason?: string | null
}

export default function ShopMyCompaniesPage() {
  const [cancelModalCompany, setCancelModalCompany] = useState<MyCompanySubscription | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  const queryClient = useQueryClient()

  const { data: subscriptions, isLoading, isError, refetch } = useQuery<MyCompanySubscription[]>({
    queryKey: ['my-companies'],
    queryFn: async () => {
      const res = await api.get<MyCompanySubscription[]>('/v1/my/companies/')
      return res.data
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async (companyId: number) => {
      const res = await api.delete(`/v1/directory/companies/${companyId}/subscribe/`)
      return res.data
    },
    onSuccess: (data: { detail?: string }) => {
      setActionSuccess(data.detail || 'Obuna muvaffaqiyatli bekor qilindi.')
      setActionError(null)
      setCancelModalCompany(null)
      void queryClient.invalidateQueries({ queryKey: ['my-companies'] })
      void queryClient.invalidateQueries({ queryKey: ['shop-directory'] })
      void queryClient.invalidateQueries({ queryKey: ['shop-companies'] })
    },
    onError: (err) => {
      setActionError(apiErrorMessage(err, 'Obunani bekor qilishda xatolik yuz berdi'))
      setCancelModalCompany(null)
    },
  })

  return (
    <div className="shop-my-companies-container">
      <div className="shop-page-heading">
        <div>
          <span className="shop-eyebrow">HAMKORLARIM</span>
          <h1>Mening distribyutorlarim</h1>
          <p>
            Siz obuna bo‘lgan distribyutorlar. Ularning mahsulotlarini ko‘rish va yangi buyurtmalar berish mumkin.
          </p>
        </div>
        <Link to="/shop/directory" className="shop-primary-button">
          Distribyutorlar katalogi <ArrowRight size={15} />
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

      {isLoading ? (
        <div className="shop-skeletons" aria-label="Yuklanmoqda">
          <i />
          <i />
          <i />
        </div>
      ) : isError ? (
        <div className="shop-empty-state">
          <strong>Distribyutorlar ro‘yxatini yuklab bo‘lmadi</strong>
          <button className="shop-secondary-button" type="button" onClick={() => void refetch()}>
            Qayta urinish
          </button>
        </div>
      ) : !subscriptions || subscriptions.length === 0 ? (
        <div className="shop-empty-state">
          <span className="shop-empty-icon">
            <Building2 size={24} />
          </span>
          <strong>Siz hali hech bir distribyutorga obuna bo‘lmagansiz</strong>
          <p>Katalogdan mos keluvchi distribyutorlarni tanlab, hamkorlikni boshlang.</p>
          <Link to="/shop/directory" className="shop-primary-button" style={{ marginTop: 12 }}>
            Distribyutorlar katalogi <ArrowRight size={15} />
          </Link>
        </div>
      ) : (
        <div className="shop-directory-grid">
          {subscriptions.map((sub) => (
            <article key={sub.id} className="shop-directory-card">
              <div className="shop-directory-card-header">
                <div className="shop-directory-logo">
                  {sub.company_logo ? (
                    <img src={sub.company_logo} alt={sub.company_name} />
                  ) : (
                    <Building2 size={26} strokeWidth={1.5} />
                  )}
                </div>
                <div className="shop-directory-header-meta">
                  <h3>{sub.company_name}</h3>
                  {sub.company_phone && (
                    <a href={`tel:${sub.company_phone}`} className="shop-directory-phone">
                      <Phone size={13} /> {sub.company_phone}
                    </a>
                  )}
                </div>
              </div>

              <div className="shop-directory-details">
                <div className="shop-directory-detail-row">
                  <span className="detail-label">
                    <Clock size={13} /> Cutoff vaqti:
                  </span>
                  <strong className="detail-value">
                    {sub.company_order_cutoff_time.slice(0, 5)} gacha
                  </strong>
                </div>

                <div className="shop-directory-detail-row">
                  <span className="detail-label">Obuna holati:</span>
                  {sub.status === 'active' && (
                    <span className="subscription-badge active">
                      <CheckCircle2 size={12} /> Faol
                    </span>
                  )}
                  {sub.status === 'pending' && (
                    <span className="subscription-badge pending">
                      <Clock size={12} /> Kutilmoqda
                    </span>
                  )}
                  {sub.status === 'blocked' && (
                    <span className="subscription-badge blocked">
                      <ShieldAlert size={12} /> Bloklangan
                    </span>
                  )}
                  {sub.status === 'rejected' && (
                    <span className="subscription-badge blocked">Rad etilgan</span>
                  )}
                </div>
              </div>

              <div className="shop-directory-card-actions">
                {sub.status === 'active' && (
                  <div className="status-action-row">
                    <Link
                      to={`/shop/catalog?company=${sub.company_id}`}
                      className="shop-primary-button shop-button-sm"
                    >
                      <Package size={14} /> Katalogga o‘tish
                    </Link>
                    <button
                      type="button"
                      className="shop-text-button-danger"
                      onClick={() => setCancelModalCompany(sub)}
                    >
                      Obunani bekor qilish
                    </button>
                  </div>
                )}

                {sub.status === 'pending' && (
                  <p className="status-hint">
                    Kompaniya tomonidan tasdiqlanishi kutilmoqda. Tasdiqlangach tovarlariga buyurtma bera olasiz.
                  </p>
                )}

                {sub.status === 'rejected' && sub.reject_reason && (
                  <p className="status-hint" style={{ color: '#dc2626' }}>
                    Sabab: {sub.reject_reason}
                  </p>
                )}
              </div>
            </article>
          ))}
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
              <strong>{cancelModalCompany.company_name}</strong> distribyutoriga obunani bekor qilmoqchimisiz?
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
                onClick={() => cancelMutation.mutate(cancelModalCompany.company_id)}
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
