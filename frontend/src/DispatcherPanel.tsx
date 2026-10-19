import {
  BarChart3,
  Ban,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock3,
  LogOut,
  Moon,
  Package,
  RotateCw,
  Search,
  Sun,
  Truck,
  X,
  Route as RouteIcon,
  Boxes,
} from 'lucide-react'
import { Fragment } from 'react'
import { useEffect, useState, type KeyboardEvent, type ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import axios from 'axios'
import api, { apiErrorMessage } from './api'
import { useAuth } from './useAuth'
import {
  buildOrderQueryParams,
  canTransitionOrder,
  formatCurrency,
  formatOrderDate,
  orderStatusLabels,
  selectNewOrders,
  toggleOrderSelection,
  type OrderFilters,
  type OrderStatus,
} from './dispatcherUtils'
import './DispatcherPanel.css'
import './DispatcherPlanning.css'
import './DispatcherOrders.css'

const TripPlanningPage = lazy(() => import('./TripPlanningPage'))
const PickingListPage = lazy(() => import('./PickingListPage'))

type DashboardData = {
  date: string
  orders_total: number
  total_volume: string
  delivered: number
  pending: number
  overdue_stops: number
  trips_by_status: Record<string, number>
}

type AdminOrder = {
  id: number
  company_name: string
  shop_id: number
  status: OrderStatus
  delivery_date: string
  delivery_time_from: string | null
  delivery_time_to: string | null
  total_price: string
  created_at: string
  shop_name: string
}

type AdminOrderDetail = AdminOrder & {
  note: string
  items: Array<{
    id: number
    product_name: string
    unit: string
    quantity: string
    unit_price: string
    line_total: string
  }>
  status_history: Array<{
    from_status: OrderStatus | null
    status: OrderStatus
    actor_phone: string | null
    note: string
    created_at: string
  }>
}

type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

const statuses: OrderStatus[] = [
  'new',
  'confirmed',
  'loaded',
  'in_transit',
  'delivered',
  'cancelled',
]

const tripStatusLabels: Record<string, string> = {
  planned: 'Rejalashtirilgan',
  confirmed: 'Tasdiqlangan',
  in_progress: 'Yo‘lda',
  completed: 'Yakunlangan',
  cancelled: 'Bekor qilingan',
}

function localDate() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function DispatcherThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <button
      type="button"
      className="dispatcher-icon-button"
      aria-label={dark ? 'Yorug‘ rejimga o‘tish' : 'Qorong‘i rejimga o‘tish'}
      onClick={() => setDark((value) => !value)}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  )
}

function DispatcherPanel() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [logoutError, setLogoutError] = useState('')

  if (!user || user.role !== 'company_admin') {
    return <Navigate to="/" replace />
  }

  const signOut = async () => {
    setLogoutError('')
    try {
      await logout()
      navigate('/staff/login', { replace: true })
    } catch {
      setLogoutError('Tizimdan chiqib bo‘lmadi. Qayta urinib ko‘ring.')
    }
  }

  const pageTitle = location.pathname.startsWith('/company/orders')
    ? 'Buyurtmalar'
    : location.pathname.startsWith('/company/trips')
      ? 'Reys tuzish'
      : location.pathname.startsWith('/company/picking-list')
        ? 'Yuklash ro‘yxati'
        : 'Umumiy ko‘rinish'

  return (
    <div className="dispatcher-shell">
      <aside className="dispatcher-sidebar">
        <NavLink to="/company" end className="dispatcher-brand">
          <span className="dispatcher-brand-mark">t</span>
          <span><strong>tarqatuv</strong><small>Boshqaruv oynasi</small></span>
        </NavLink>
        <div className="dispatcher-side-label">BOSHQARUV</div>
        <nav className="dispatcher-nav" aria-label="Boshqaruv menyusi">
          <NavLink to="/company" end className={({ isActive }) => `dispatcher-nav-link ${isActive ? 'dispatcher-nav-active' : ''}`}>
            <BarChart3 size={18} strokeWidth={1.8} /><span>Umumiy ko‘rinish</span>
          </NavLink>
          <NavLink to="/company/orders" className={({ isActive }) => `dispatcher-nav-link ${isActive ? 'dispatcher-nav-active' : ''}`}>
            <ClipboardList size={18} strokeWidth={1.8} /><span>Buyurtmalar</span>
          </NavLink>
          <NavLink to="/company/trips" className={({ isActive }) => `dispatcher-nav-link ${isActive ? 'dispatcher-nav-active' : ''}`}>
            <RouteIcon size={18} strokeWidth={1.8} /><span>Reyslar va marshrut</span>
          </NavLink>
          <NavLink to="/company/picking-list" className={({ isActive }) => `dispatcher-nav-link ${isActive ? 'dispatcher-nav-active' : ''}`}>
            <Boxes size={18} strokeWidth={1.8} /><span>Yuklash ro‘yxati</span>
          </NavLink>
        </nav>
        <div className="dispatcher-sidebar-bottom">
          <div className="dispatcher-account">
            <span className="dispatcher-avatar">{user.phone.slice(-2)}</span>
            <span><strong>{user.phone}</strong><small>Kompaniya boshqaruvchisi</small></span>
          </div>
          {logoutError && <p className="dispatcher-error" role="alert">{logoutError}</p>}
          <button type="button" className="dispatcher-logout" onClick={() => void signOut()}>
            <LogOut size={16} /> Tizimdan chiqish
          </button>
        </div>
      </aside>
      <main className="dispatcher-main">
        <header className="dispatcher-topbar">
          <div className="dispatcher-breadcrumb">Tarqatuv <span>/</span> {pageTitle}</div>
          <div className="dispatcher-top-actions">
            <span className="dispatcher-today"><CalendarDays size={15} /> {formatOrderDate(localDate())}</span>
            <DispatcherThemeToggle />
          </div>
        </header>
        <div className="dispatcher-content">
          <Routes>
            <Route index element={<DashboardPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="trips" element={<Suspense fallback={<LoadingState />}><TripPlanningPage /></Suspense>} />
            <Route path="picking-list" element={<Suspense fallback={<LoadingState />}><PickingListPage /></Suspense>} />
            <Route path="*" element={<Navigate to="/company" replace />} />
          </Routes>
        </div>
        <nav className="dispatcher-mobile-nav" aria-label="Mobil boshqaruv menyusi">
          <NavLink to="/company" end className={({ isActive }) => isActive ? 'dispatcher-mobile-active' : ''}>
            <BarChart3 size={19} /><small>Umumiy</small>
          </NavLink>
          <NavLink to="/company/orders" className={({ isActive }) => isActive ? 'dispatcher-mobile-active' : ''}>
            <ClipboardList size={19} /><small>Buyurtmalar</small>
          </NavLink>
          <NavLink to="/company/trips" className={({ isActive }) => isActive ? 'dispatcher-mobile-active' : ''}>
            <RouteIcon size={19} /><small>Reyslar</small>
          </NavLink>
          <NavLink to="/company/picking-list" className={({ isActive }) => isActive ? 'dispatcher-mobile-active' : ''}>
            <Boxes size={19} /><small>Yuklash</small>
          </NavLink>
        </nav>
      </main>
    </div>
  )
}

function PageHeading({ title, description }: { title: string; description: string }) {
  return (
    <div className="dispatcher-page-heading">
      <div>
        <span className="dispatcher-eyebrow">KOMPANIYA BOSHQARUVI</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </div>
  )
}

function DashboardPage() {
  const dashboard = useQuery({
    queryKey: ['dispatcher-dashboard'],
    queryFn: async () => (await api.get<DashboardData>('/v1/admin/dashboard/')).data,
  })

  return (
    <>
      <PageHeading title="Bugungi holat" description="Buyurtmalar va yetkazib berish ishlarini bir joyda kuzating." />
      {dashboard.isLoading ? (
        <LoadingState />
      ) : dashboard.isError ? (
        <ErrorState message={apiErrorMessage(dashboard.error, 'Boshqaruv ma’lumotlarini yuklab bo‘lmadi.')} onRetry={() => void dashboard.refetch()} />
      ) : dashboard.data ? (
        <>
          <section className="dispatcher-metrics" aria-label="Bugungi ko‘rsatkichlar">
            <MetricCard icon={<ClipboardList size={18} />} label="Buyurtmalar" value={dashboard.data.orders_total} />
            <MetricCard icon={<Clock3 size={18} />} label="Kutilayotgan" value={dashboard.data.pending} tone="amber" />
            <MetricCard icon={<CheckCircle2 size={18} />} label="Yetkazilgan" value={dashboard.data.delivered} tone="green" />
            <MetricCard icon={<Package size={18} />} label="Jami hajm" value={dashboard.data.total_volume} />
            <MetricCard icon={<Clock3 size={18} />} label="Kechikkan nuqtalar" value={dashboard.data.overdue_stops} tone="red" />
            <MetricCard
              icon={<Truck size={18} />}
              label="Faol reyslar"
              value={(dashboard.data.trips_by_status.confirmed ?? 0) + (dashboard.data.trips_by_status.in_progress ?? 0)}
            />
          </section>
          <section className="dispatcher-card dispatcher-trip-summary">
            <div className="dispatcher-section-heading">
              <div><span className="dispatcher-eyebrow">YETKAZIB BERISH</span><h2>Reyslar holati</h2></div>
              <Truck size={19} />
            </div>
            <div className="dispatcher-trip-statuses">
              {Object.entries(tripStatusLabels).map(([status, label]) => (
                <div className="dispatcher-trip-status" key={status}>
                  <span>{label}</span><strong>{dashboard.data?.trips_by_status[status] ?? 0}</strong>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </>
  )
}

function MetricCard({
  icon,
  label,
  value,
  tone = 'default',
}: {
  icon: ReactNode
  label: string
  value: string | number
  tone?: 'default' | 'amber' | 'green' | 'red'
}) {
  return (
    <article className={`dispatcher-metric dispatcher-metric-${tone}`}>
      <span className="dispatcher-metric-icon">{icon}</span>
      <span className="dispatcher-metric-label">{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function OrdersPage() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<OrderFilters>({
    date: localDate(),
    status: 'all',
    search: '',
    page: 1,
  })
  const [selectedOrderIds, setSelectedOrderIds] = useState<number[]>([])
  const [expandedOrderId, setExpandedOrderId] = useState<number | null>(null)
  const [cancelOrderId, setCancelOrderId] = useState<number | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [actionError, setActionError] = useState('')
  const [creditWarning, setCreditWarning] = useState<{
    orderIds: number[]
    bulk: boolean
    message: string
  } | null>(null)
  const orders = useQuery({
    queryKey: ['dispatcher-orders', filters],
    queryFn: async () => (
      await api.get<Page<AdminOrder>>('/v1/admin/orders/', {
        params: buildOrderQueryParams(filters),
      })
    ).data,
  })
  const orderDetail = useQuery({
    queryKey: ['dispatcher-order-detail', expandedOrderId],
    queryFn: async () => (
      await api.get<AdminOrderDetail>(`/v1/admin/orders/${expandedOrderId}/`)
    ).data,
    enabled: expandedOrderId !== null,
  })
  const pageCount = orders.data ? Math.max(1, Math.ceil(orders.data.count / 25)) : 1
  const pageOrders = orders.data?.results ?? []
  const newOrders = pageOrders.filter((order) => order.status === 'new')
  const allNewOrdersSelected = newOrders.length > 0 &&
    newOrders.every((order) => selectedOrderIds.includes(order.id))

  const refreshOrders = async (orderIds: number[]) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['dispatcher-orders'] }),
      queryClient.invalidateQueries({ queryKey: ['dispatcher-dashboard'] }),
      ...orderIds.map((id) => queryClient.invalidateQueries({
        queryKey: ['dispatcher-order-detail', id],
      })),
    ])
  }

  const confirmOrders = useMutation({
    mutationFn: async (request: { orderIds: number[]; bulk: boolean; allowCreditLimitExceeded: boolean }) => {
      if (request.bulk) {
        await api.post('/v1/admin/orders/bulk-confirm/', {
          order_ids: request.orderIds,
          reason: 'Dispetcher tomonidan tasdiqlandi',
          allow_credit_limit_exceeded: request.allowCreditLimitExceeded,
        })
      } else {
        await api.post(`/v1/admin/orders/${request.orderIds[0]}/status/`, {
          status: 'confirmed',
          reason: 'Dispetcher tomonidan tasdiqlandi',
          allow_credit_limit_exceeded: request.allowCreditLimitExceeded,
        })
      }
      return request.orderIds
    },
    onSuccess: async (orderIds) => {
      setActionError('')
      setCreditWarning(null)
      setSelectedOrderIds((current) => current.filter((id) => !orderIds.includes(id)))
      await refreshOrders(orderIds)
    },
    onError: (error, request) => {
      const warning = axios.isAxiosError(error) && typeof error.response?.data?.warning === 'string'
        ? error.response.data.warning
        : null
      if (warning) {
        setCreditWarning({ orderIds: request.orderIds, bulk: request.bulk, message: warning })
        setActionError('')
      } else {
        setActionError(apiErrorMessage(error, 'Buyurtmani tasdiqlab bo‘lmadi. Qayta urinib ko‘ring.'))
      }
    },
  })

  const cancelOrder = useMutation({
    mutationFn: async (request: { orderId: number; reason: string }) => {
      await api.post(`/v1/admin/orders/${request.orderId}/status/`, {
        status: 'cancelled',
        reason: request.reason,
      })
      return request.orderId
    },
    onSuccess: async (orderId) => {
      setActionError('')
      setCancelOrderId(null)
      setCancelReason('')
      setSelectedOrderIds((current) => current.filter((id) => id !== orderId))
      await refreshOrders([orderId])
    },
  })

  const updateFilter = <K extends keyof OrderFilters>(key: K, value: OrderFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }))
    setSelectedOrderIds([])
    setCreditWarning(null)
    setActionError('')
  }
  const toggleOrderDetails = (orderId: number) => {
    setExpandedOrderId((current) => current === orderId ? null : orderId)
  }
  const handleOrderRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, orderId: number) => {
    if (event.target !== event.currentTarget || !['Enter', ' '].includes(event.key)) return
    event.preventDefault()
    toggleOrderDetails(orderId)
  }
  const closeCancelDialog = () => {
    if (cancelOrder.isPending) return
    setCancelOrderId(null)
    setCancelReason('')
    cancelOrder.reset()
  }

  return (
    <>
      <PageHeading title="Buyurtmalar" description="Kompaniyangiz buyurtmalarini sana, holat va qidiruv bo‘yicha ko‘ring." />
      <section className="dispatcher-card dispatcher-orders-card">
        <div className="dispatcher-orders-toolbar">
          <label className="dispatcher-filter">
            <span>Sana</span>
            <input type="date" value={filters.date} onChange={(event) => updateFilter('date', event.target.value)} />
          </label>
          <label className="dispatcher-filter">
            <span>Holat</span>
            <select value={filters.status} onChange={(event) => updateFilter('status', event.target.value as OrderStatus | 'all')}>
              <option value="all">Barcha holatlar</option>
              {statuses.map((status) => <option key={status} value={status}>{orderStatusLabels[status]}</option>)}
            </select>
          </label>
          <label className="dispatcher-search">
            <Search size={17} />
            <input
              type="search"
              value={filters.search}
              onChange={(event) => updateFilter('search', event.target.value)}
              placeholder="Do‘kon, telefon yoki buyurtma raqami"
              aria-label="Buyurtmalarni qidirish"
            />
            {filters.search && <button type="button" aria-label="Qidiruvni tozalash" onClick={() => updateFilter('search', '')}><X size={15} /></button>}
          </label>
        </div>
        {selectedOrderIds.length > 0 && (
          <div className="dispatcher-bulk-actions">
            <span>{selectedOrderIds.length} ta yangi buyurtma tanlandi</span>
            <button
              type="button"
              className="dispatcher-order-action dispatcher-order-confirm"
              disabled={confirmOrders.isPending}
              onClick={() => {
                setActionError('')
                setCreditWarning(null)
                confirmOrders.mutate({
                  orderIds: selectedOrderIds,
                  bulk: true,
                  allowCreditLimitExceeded: false,
                })
              }}
            >
              <Check size={14} /> Hammasini tasdiqlash
            </button>
          </div>
        )}
        {actionError && <div className="dispatcher-action-error" role="alert">{actionError}</div>}
        {creditWarning && (
          <div className="dispatcher-credit-warning" role="alert">
            <span>{creditWarning.message} Bu buyurtmalarni limitdan oshirib tasdiqlashga ruxsat berasizmi?</span>
            <div>
              <button
                type="button"
                className="dispatcher-order-action dispatcher-order-confirm"
                disabled={confirmOrders.isPending}
                onClick={() => confirmOrders.mutate({
                  orderIds: creditWarning.orderIds,
                  bulk: creditWarning.bulk,
                  allowCreditLimitExceeded: true,
                })}
              >
                Limitdan oshirib tasdiqlash
              </button>
              <button type="button" className="dispatcher-order-action" onClick={() => setCreditWarning(null)}>
                Rad etish
              </button>
            </div>
          </div>
        )}
        {orders.isLoading ? <LoadingState /> : orders.isError ? (
          <ErrorState message={apiErrorMessage(orders.error, 'Buyurtmalarni yuklab bo‘lmadi.')} onRetry={() => void orders.refetch()} />
        ) : orders.data?.results.length ? (
          <>
            <div className="dispatcher-table-scroll">
              <table className="dispatcher-orders-table">
                <thead>
                  <tr>
                    <th>
                      <input
                        type="checkbox"
                        aria-label="Sahifadagi yangi buyurtmalarni tanlash"
                        checked={allNewOrdersSelected}
                        disabled={!newOrders.length}
                        onChange={(event) => setSelectedOrderIds((current) => (
                          selectNewOrders(current, pageOrders, event.target.checked)
                        ))}
                      />
                    </th>
                    <th>Buyurtma</th>
                    <th>Do‘kon</th>
                    <th>Yetkazish sanasi</th>
                    <th>Holati</th>
                    <th>Summa</th>
                    <th>Amallar</th>
                  </tr>
                </thead>
                <tbody>
                  {pageOrders.map((order) => {
                    const isExpanded = expandedOrderId === order.id
                    const canConfirm = canTransitionOrder(order.status, 'confirmed')
                    const canCancel = canTransitionOrder(order.status, 'cancelled')
                    return (
                      <Fragment key={order.id}>
                        <tr
                          className="dispatcher-order-row"
                          tabIndex={0}
                          aria-expanded={isExpanded}
                          onClick={() => toggleOrderDetails(order.id)}
                          onKeyDown={(event) => handleOrderRowKeyDown(event, order.id)}
                        >
                          <td>
                            {order.status === 'new' && (
                              <input
                                type="checkbox"
                                aria-label={`Buyurtma #${order.id} ni tanlash`}
                                checked={selectedOrderIds.includes(order.id)}
                                onClick={(event) => event.stopPropagation()}
                                onChange={() => setSelectedOrderIds((current) => (
                                  toggleOrderSelection(current, order.id)
                                ))}
                              />
                            )}
                          </td>
                          <td><strong>#{order.id}</strong><small>{order.company_name}</small></td>
                          <td>{order.shop_name}</td>
                          <td>{formatOrderDate(order.delivery_date)}{order.delivery_time_from && order.delivery_time_to ? <small>{order.delivery_time_from}–{order.delivery_time_to}</small> : null}</td>
                          <td><span className={`dispatcher-status dispatcher-status-${order.status}`}>{orderStatusLabels[order.status]}</span></td>
                          <td className="dispatcher-order-total">{formatCurrency(order.total_price)}</td>
                          <td>
                            <div className="dispatcher-row-actions" onClick={(event) => event.stopPropagation()}>
                              {canConfirm && (
                                <button
                                  type="button"
                                  className="dispatcher-order-action dispatcher-order-confirm"
                                  disabled={confirmOrders.isPending}
                                  onClick={() => {
                                    setActionError('')
                                    setCreditWarning(null)
                                    confirmOrders.mutate({
                                      orderIds: [order.id],
                                      bulk: false,
                                      allowCreditLimitExceeded: false,
                                    })
                                  }}
                                >
                                  <Check size={13} /> Tasdiqlash
                                </button>
                              )}
                              {canCancel && (
                                <button
                                  type="button"
                                  className="dispatcher-order-action dispatcher-order-cancel"
                                  onClick={() => {
                                    cancelOrder.reset()
                                    setCancelOrderId(order.id)
                                    setCancelReason('')
                                    setActionError('')
                                  }}
                                >
                                  <Ban size={13} /> Bekor qilish
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="dispatcher-order-detail-row">
                            <td colSpan={7}>
                              {orderDetail.isLoading ? (
                                <div className="dispatcher-order-detail-loading" role="status">Buyurtma tafsiloti yuklanmoqda…</div>
                              ) : orderDetail.isError ? (
                                <div className="dispatcher-order-detail-error" role="alert">
                                  <span>{apiErrorMessage(orderDetail.error, 'Buyurtma tafsilotini yuklab bo‘lmadi.')}</span>
                                  <button type="button" onClick={() => void orderDetail.refetch()}>Qayta urinish</button>
                                </div>
                              ) : orderDetail.data?.id === order.id ? (
                                <OrderDetails order={orderDetail.data} />
                              ) : null}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <footer className="dispatcher-pagination">
              <span>{orders.data.count} ta buyurtmadan {filters.page}-sahifa / {pageCount}</span>
              <div>
                <button type="button" aria-label="Oldingi sahifa" disabled={!orders.data.previous} onClick={() => setFilters((current) => ({ ...current, page: Math.max(1, current.page - 1) }))}><ChevronLeft size={17} /></button>
                <button type="button" aria-label="Keyingi sahifa" disabled={!orders.data.next} onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}><ChevronRight size={17} /></button>
              </div>
            </footer>
          </>
        ) : (
          <div className="dispatcher-empty"><ClipboardList size={22} /><strong>Buyurtmalar topilmadi</strong><span>Tanlangan filtrlarni o‘zgartirib ko‘ring.</span></div>
        )}
      </section>
      {cancelOrderId !== null && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeCancelDialog()
        }}>
          <form
            className="dispatcher-confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-cancel-title"
            onSubmit={(event) => {
              event.preventDefault()
              cancelOrder.mutate({ orderId: cancelOrderId, reason: cancelReason.trim() })
            }}
          >
            <h2 id="dispatcher-cancel-title">Buyurtmani bekor qilish</h2>
            <p>#{cancelOrderId} buyurtmani bekor qilish sababini kiriting.</p>
            <label>
              <span>Bekor qilish sababi</span>
              <textarea
                autoFocus
                required
                maxLength={500}
                value={cancelReason}
                onChange={(event) => setCancelReason(event.target.value)}
              />
            </label>
            {cancelMutationError(cancelOrder) && (
              <p className="dispatcher-dialog-error" role="alert">{cancelMutationError(cancelOrder)}</p>
            )}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={cancelOrder.isPending} onClick={closeCancelDialog}>
                Ortga
              </button>
              <button type="submit" className="dispatcher-order-action dispatcher-order-cancel" disabled={!cancelReason.trim() || cancelOrder.isPending}>
                {cancelOrder.isPending ? 'Bekor qilinmoqda…' : 'Bekor qilish'}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}

function cancelMutationError(mutation: { error: unknown }) {
  return mutation.error
    ? apiErrorMessage(mutation.error, 'Buyurtmani bekor qilib bo‘lmadi. Qayta urinib ko‘ring.')
    : ''
}

function OrderDetails({ order }: { order: AdminOrderDetail }) {
  const unitLabels: Record<string, string> = { piece: 'dona', box: 'quti', block: 'blok' }
  return (
    <section className="dispatcher-order-details" aria-label={`Buyurtma #${order.id} tafsiloti`}>
      <div className="dispatcher-order-detail-heading">
        <h3>Buyurtma #{order.id} tafsiloti</h3>
        <strong>{formatCurrency(order.total_price)}</strong>
      </div>
      <h4>Mahsulotlar</h4>
      {order.items.length ? (
        <div className="dispatcher-detail-items">
          {order.items.map((item) => (
            <div className="dispatcher-detail-item" key={item.id}>
              <strong>{item.product_name}</strong>
              <span>{item.quantity} {unitLabels[item.unit] ?? item.unit} × {formatCurrency(item.unit_price)}</span>
              <b>{formatCurrency(item.line_total)}</b>
            </div>
          ))}
        </div>
      ) : <p className="dispatcher-detail-note">Mahsulotlar topilmadi.</p>}
      <div className="dispatcher-order-detail-meta">
        <div><h4>Izoh</h4><p className="dispatcher-detail-note">{order.note || 'Izoh yo‘q'}</p></div>
        <div>
          <h4>Holat tarixi</h4>
          {order.status_history.length ? (
            <ol className="dispatcher-order-history">
              {order.status_history.map((entry, index) => (
                <li key={`${entry.created_at}-${index}`}>
                  <strong>{entry.from_status ? orderStatusLabels[entry.from_status] : 'Yaratildi'} → {orderStatusLabels[entry.status]}</strong>
                  <span>{new Date(entry.created_at).toLocaleString('uz-UZ', {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                    timeZone: 'Asia/Tashkent',
                  })}</span>
                  <span>{entry.actor_phone ? `Mas’ul: ${entry.actor_phone}` : 'Mas’ul: tizim'}</span>
                  {entry.note && <small>{entry.note}</small>}
                </li>
              ))}
            </ol>
          ) : <p className="dispatcher-detail-note">Holat tarixi hali yo‘q.</p>}
        </div>
      </div>
    </section>
  )
}

function LoadingState() {
  return <div className="dispatcher-loading" role="status"><span /> Ma’lumot yuklanmoqda…</div>
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="dispatcher-error-state" role="alert">
      <p>{message}</p>
      <button type="button" onClick={onRetry}><RotateCw size={15} /> Qayta urinish</button>
    </div>
  )
}

export default DispatcherPanel
