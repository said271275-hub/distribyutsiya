import {
  BarChart3,
  CalendarDays,
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
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import { useAuth } from './useAuth'
import {
  buildOrderQueryParams,
  formatCurrency,
  formatOrderDate,
  orderStatusLabels,
  type OrderFilters,
  type OrderStatus,
} from './dispatcherUtils'
import './DispatcherPanel.css'

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

  const onOrdersPage = location.pathname.startsWith('/company/orders')

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
          <div className="dispatcher-breadcrumb">Tarqatuv <span>/</span> {onOrdersPage ? 'Buyurtmalar' : 'Umumiy ko‘rinish'}</div>
          <div className="dispatcher-top-actions">
            <span className="dispatcher-today"><CalendarDays size={15} /> {formatOrderDate(localDate())}</span>
            <DispatcherThemeToggle />
          </div>
        </header>
        <div className="dispatcher-content">
          <Routes>
            <Route index element={<DashboardPage />} />
            <Route path="orders" element={<OrdersPage />} />
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
  const [filters, setFilters] = useState<OrderFilters>({
    date: localDate(),
    status: 'all',
    search: '',
    page: 1,
  })
  const orders = useQuery({
    queryKey: ['dispatcher-orders', filters],
    queryFn: async () => (
      await api.get<Page<AdminOrder>>('/v1/admin/orders/', {
        params: buildOrderQueryParams(filters),
      })
    ).data,
  })
  const pageCount = orders.data ? Math.max(1, Math.ceil(orders.data.count / 25)) : 1

  const updateFilter = <K extends keyof OrderFilters>(key: K, value: OrderFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }))
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
        {orders.isLoading ? <LoadingState /> : orders.isError ? (
          <ErrorState message={apiErrorMessage(orders.error, 'Buyurtmalarni yuklab bo‘lmadi.')} onRetry={() => void orders.refetch()} />
        ) : orders.data?.results.length ? (
          <>
            <div className="dispatcher-table-scroll">
              <table className="dispatcher-orders-table">
                <thead>
                  <tr>
                    <th>Buyurtma</th>
                    <th>Do‘kon</th>
                    <th>Yetkazish sanasi</th>
                    <th>Holati</th>
                    <th>Summa</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.data.results.map((order) => (
                    <tr key={order.id}>
                      <td><strong>#{order.id}</strong><small>{order.company_name}</small></td>
                      <td>Do‘kon #{order.shop_id}</td>
                      <td>{formatOrderDate(order.delivery_date)}{order.delivery_time_from && order.delivery_time_to ? <small>{order.delivery_time_from}–{order.delivery_time_to}</small> : null}</td>
                      <td><span className={`dispatcher-status dispatcher-status-${order.status}`}>{orderStatusLabels[order.status]}</span></td>
                      <td className="dispatcher-order-total">{formatCurrency(order.total_price)}</td>
                    </tr>
                  ))}
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
    </>
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
