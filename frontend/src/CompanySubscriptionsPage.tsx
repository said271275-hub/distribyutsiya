import {
  Ban,
  Calendar,
  Check,
  Clock,
  Filter,
  MapPin,
  Phone,
  RefreshCw,
  Search,
  UserCheck,
  UsersRound,
  X,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import './DispatcherPanel.css'

export type SubscriptionItem = {
  id: number
  shop_id: number
  shop_name: string
  district: string
  requested_at: string
  decided_at: string | null
  status: 'pending' | 'active' | 'rejected' | 'blocked'
  phone_primary: string | null
  address: string | null
  reject_reason: string
}

export default function CompanySubscriptionsPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'pending' | 'active' | 'all'>('pending')
  const [search, setSearch] = useState('')
  const [rejectDialogItem, setRejectDialogItem] = useState<SubscriptionItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [blockDialogItem, setBlockDialogItem] = useState<SubscriptionItem | null>(null)
  const [successMessage, setSuccessMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const subscriptionsQuery = useQuery({
    queryKey: ['company-subscriptions', tab],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (tab !== 'all') {
        params.status = tab
      }
      // Backend oddiy massiv qaytaradi; sahifalangan ({ results }) javobni ham qo'llab-quvvatlaymiz.
      const { data } = await api.get<SubscriptionItem[] | { results: SubscriptionItem[] }>('/v1/company/subscriptions/', { params })
      return Array.isArray(data) ? data : (data.results ?? [])
    },
  })

  const actionMutation = useMutation({
    mutationFn: async ({ id, action, data }: { id: number; action: string; data?: { reject_reason?: string } }) => {
      return (await api.post(`/v1/company/subscriptions/${id}/${action}/`, data || {})).data
    },
    onSuccess: (_, vars) => {
      const actionText =
        vars.action === 'approve'
          ? 'Obuna muvaffaqiyatli tasdiqlandi.'
          : vars.action === 'reject'
            ? 'Obuna so‘rovi rad etildi.'
            : 'Do‘kon bloklandi.'
      setSuccessMessage(actionText)
      setErrorMessage('')
      setRejectDialogItem(null)
      setRejectReason('')
      setBlockDialogItem(null)
      void queryClient.invalidateQueries({ queryKey: ['company-subscriptions'] })
      void queryClient.invalidateQueries({ queryKey: ['dispatcher-dashboard'] })
      setTimeout(() => setSuccessMessage(''), 4000)
    },
    onError: (error) => {
      setErrorMessage(apiErrorMessage(error, 'Amalni bajarib bo‘lmadi.'))
    },
  })

  const items = subscriptionsQuery.data ?? []
  const filteredItems = items.filter((item) =>
    search ? item.shop_name.toLowerCase().includes(search.toLowerCase()) || item.district.toLowerCase().includes(search.toLowerCase()) : true,
  )

  const statusBadges: Record<string, { label: string; tone: string }> = {
    pending: { label: 'Kutilmoqda', tone: 'dispatcher-badge-amber' },
    active: { label: 'Faol do‘kon', tone: 'dispatcher-badge-green' },
    rejected: { label: 'Rad etilgan', tone: 'dispatcher-badge-red' },
    blocked: { label: 'Bloklangan', tone: 'dispatcher-badge-red' },
  }

  return (
    <div className="dispatcher-subscriptions-page">
      <div className="dispatcher-section-heading">
        <div>
          <span className="dispatcher-eyebrow">HAMKORLIK</span>
          <h2>Do‘konlar obunasi va so‘rovlar</h2>
          <p>Kompaniyangizga buyurtma bermoqchi bo‘lgan do‘konlar so‘rovlarini tasdiqlang yoki boshqaring.</p>
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

      <div className="dispatcher-sub-tabs-row">
        <div className="dispatcher-sub-tabs">
          <button
            type="button"
            className={`dispatcher-sub-tab ${tab === 'pending' ? 'active' : ''}`}
            onClick={() => setTab('pending')}
          >
            <Clock size={16} /> <span>Kutilayotgan so‘rovlar</span>
          </button>
          <button
            type="button"
            className={`dispatcher-sub-tab ${tab === 'active' ? 'active' : ''}`}
            onClick={() => setTab('active')}
          >
            <UserCheck size={16} /> <span>Faol do‘konlar</span>
          </button>
          <button
            type="button"
            className={`dispatcher-sub-tab ${tab === 'all' ? 'active' : ''}`}
            onClick={() => setTab('all')}
          >
            <Filter size={16} /> <span>Barchasi</span>
          </button>
        </div>

        <div className="dispatcher-search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder="Do‘kon nomi yoki tuman bo‘yicha qidirish…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {subscriptionsQuery.isLoading ? (
        <div className="dispatcher-loading" role="status">So‘rovlar yuklanmoqda…</div>
      ) : subscriptionsQuery.isError ? (
        <div className="dispatcher-error-state" role="alert">
          <p>{apiErrorMessage(subscriptionsQuery.error, 'So‘rovlarni yuklab bo‘lmadi.')}</p>
          <button type="button" onClick={() => void subscriptionsQuery.refetch()}>
            <RefreshCw size={15} /> Qayta urinish
          </button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="dispatcher-empty">
          <UsersRound size={26} />
          <strong>So‘rovlar topilmadi</strong>
          <span>
            {tab === 'pending'
              ? 'Hozirda kutilayotgan yangi do‘kon so‘rovlari yo‘q.'
              : 'Ushbu bo‘limda ko‘rsatish uchun obuna ma’lumotlari mavjud emas.'}
          </span>
        </div>
      ) : (
        <div className="dispatcher-subscriptions-grid">
          {filteredItems.map((item) => {
            const badge = statusBadges[item.status] ?? statusBadges.pending
            return (
              <div className="dispatcher-card dispatcher-sub-card" key={item.id}>
                <div className="dispatcher-sub-card-header">
                  <div>
                    <h4>{item.shop_name}</h4>
                    <span className="dispatcher-sub-district">
                      <MapPin size={14} /> {item.district}
                    </span>
                  </div>
                  <span className={`dispatcher-status-badge ${badge.tone}`}>{badge.label}</span>
                </div>

                <div className="dispatcher-sub-details">
                  <div className="dispatcher-sub-meta-row">
                    <Calendar size={14} />
                    <span>
                      So‘rov vaqti:{' '}
                      {new Date(item.requested_at).toLocaleDateString('uz-UZ', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>

                  {item.status === 'active' ? (
                    <>
                      {item.phone_primary && (
                        <div className="dispatcher-sub-meta-row">
                          <Phone size={14} />
                          <strong>{item.phone_primary}</strong>
                        </div>
                      )}
                      {item.address && (
                        <div className="dispatcher-sub-meta-row">
                          <MapPin size={14} />
                          <span>{item.address}</span>
                        </div>
                      )}
                    </>
                  ) : item.status === 'pending' ? (
                    <p className="dispatcher-sub-privacy-note">
                      🔒 Telefon va aniq manzil faqat obuna tasdiqlangach ochiladi.
                    </p>
                  ) : item.status === 'rejected' && item.reject_reason ? (
                    <p className="dispatcher-sub-reject-note">
                      Rad etish sababi: <i>{item.reject_reason}</i>
                    </p>
                  ) : null}
                </div>

                {item.status === 'pending' && (
                  <div className="dispatcher-sub-card-actions">
                    <button
                      type="button"
                      className="dispatcher-btn-approve"
                      disabled={actionMutation.isPending}
                      onClick={() => actionMutation.mutate({ id: item.id, action: 'approve' })}
                    >
                      <Check size={15} /> Tasdiqlash
                    </button>
                    <button
                      type="button"
                      className="dispatcher-btn-reject"
                      disabled={actionMutation.isPending}
                      onClick={() => {
                        setRejectDialogItem(item)
                        setRejectReason('')
                      }}
                    >
                      <X size={15} /> Rad etish
                    </button>
                    <button
                      type="button"
                      className="dispatcher-btn-block"
                      disabled={actionMutation.isPending}
                      onClick={() => setBlockDialogItem(item)}
                    >
                      <Ban size={15} /> Bloklash
                    </button>
                  </div>
                )}

                {item.status === 'active' && (
                  <div className="dispatcher-sub-card-actions">
                    <button
                      type="button"
                      className="dispatcher-btn-block-outline"
                      disabled={actionMutation.isPending}
                      onClick={() => setBlockDialogItem(item)}
                    >
                      <Ban size={14} /> Obunani to‘xtatish / Bloklash
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Reject Modal Dialog */}
      {rejectDialogItem && (
        <div className="dispatcher-dialog-backdrop" onClick={() => setRejectDialogItem(null)}>
          <div className="dispatcher-confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Obuna so‘rovini rad etish</h3>
            <p>
              <strong>{rejectDialogItem.shop_name}</strong> do‘koni so‘rovini rad etish sababini yozing:
            </p>
            <textarea
              rows={3}
              required
              autoFocus
              placeholder="Masalan: Ushbu hududga yetkazib berish rejalashtirilmagan…"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="dispatcher-input"
            />
            <div className="dispatcher-dialog-actions">
              <button
                type="button"
                className="dispatcher-order-action"
                onClick={() => setRejectDialogItem(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="dispatcher-order-action dispatcher-order-cancel"
                disabled={actionMutation.isPending || !rejectReason.trim()}
                onClick={() =>
                  actionMutation.mutate({
                    id: rejectDialogItem.id,
                    action: 'reject',
                    data: { reject_reason: rejectReason.trim() },
                  })
                }
              >
                Rad etishni tasdiqlash
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Block Modal Dialog */}
      {blockDialogItem && (
        <div className="dispatcher-dialog-backdrop" onClick={() => setBlockDialogItem(null)}>
          <div className="dispatcher-confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Do‘konni bloklash</h3>
            <p>
              Haqiqatan ham <strong>{blockDialogItem.shop_name}</strong> do‘konini bloklamoqchimisiz? Bloklangan
              do‘kon sizga boshqa qayta obuna so‘rovi yubora olmaydi.
            </p>
            <div className="dispatcher-dialog-actions">
              <button
                type="button"
                className="dispatcher-order-action"
                onClick={() => setBlockDialogItem(null)}
              >
                Bekor qilish
              </button>
              <button
                type="button"
                className="dispatcher-order-action dispatcher-order-cancel"
                disabled={actionMutation.isPending}
                onClick={() =>
                  actionMutation.mutate({
                    id: blockDialogItem.id,
                    action: 'block',
                  })
                }
              >
                Bloklash
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
