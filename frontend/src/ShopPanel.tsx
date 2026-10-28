import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ClipboardList,
  Compass,
  CreditCard,
  Home,
  MapPin,
  Minus,
  Package,
  Phone,
  Plus,
  Search,
  ShoppingBag,
  Sun,
  Moon,
  UserRound,
  Wallet,
  X,
} from 'lucide-react'
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Controller, useForm } from 'react-hook-form'
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'
import api, { apiErrorMessage } from './api'
import {
  financeEntryLabel,
  formatFinanceBalance,
  formatFinanceDate,
  formatFinanceMoney,
} from './dispatcherFinanceUtils'
import { useAuth } from './useAuth'
import { ru } from './i18n/ru'
import './ShopPanel.css'

const LocationPicker = lazy(() => import('./ShopMap'))

type CopyKey = keyof typeof ru
type Copy = (key: CopyKey) => string
type CompanyOption = { id: number; name: string; contact_phone: string; order_cutoff_time: string }
type ShopProfile = {
  id: number
  owner_id: number
  owner_phone: string
  name: string
  owner_name: string
  phone_primary: string
  phone_secondary: string
  address: string
  district: string
  latitude: string
  longitude: string
  sms_notifications_enabled: boolean
  company_contacts: Array<{ id: number; name: string; phone: string }>
}
type CatalogProduct = {
  id: number
  company_id: number
  company_name: string
  company_phone: string
  company_cutoff_time: string
  name: string
  image_url: string | null
  unit: 'piece' | 'box' | 'block'
  base_price: string
  unit_price: string
  discount_percent: string
}
type CartLine = { product: CatalogProduct; quantity: number }
type RepeatLastOrderCart = { items: Array<{ product: CatalogProduct; quantity: string }>; omitted_count: number }
type OrderItem = {
  id: number
  product_id: number
  product_name: string
  unit: CatalogProduct['unit']
  quantity: string
  unit_price: string
  line_total: string
}
type ShopOrder = {
  id: number
  company_id: number
  company_name: string
  status: 'new' | 'confirmed' | 'loaded' | 'in_transit' | 'delivered' | 'cancelled'
  delivery_date: string
  delivery_time_from: string | null
  delivery_time_to: string | null
  total_price: string
  note: string
  items: OrderItem[]
  status_history: Array<{ status: ShopOrder['status']; actor_phone: string | null; note: string; created_at: string }>
  delivery_issue_history: Array<{
    reason: string
    note: string
    delivered_items: Array<{ item_id: number; quantity: string }>
    created_at: string
  }>
  eta: string | null
  driver_phone: string | null
  created_at: string
}
type Page<T> = { results: T[]; count: number; next?: string | null; previous?: string | null }
type Finance = {
  balance: string
  balances: Array<{ company_id: number; company_name: string; balance: string; container_deposit: string }>
  payments: Array<{ id: number; company_name: string; amount: string; method: string; status: string; paid_at: string | null; created_at: string; reference: string }>
  entries: Array<{
    id: number
    company_id: number
    amount: string
    direction: 'debit' | 'credit'
    order_id: number | null
    payment_id: number | null
    note: string
    posted_at: string | null
    created_at: string
  }>
}

const uz: Record<CopyKey, string> = {
  home: 'Umumiy', catalog: 'Katalog', cart: 'Savat', orders: 'Buyurtmalar',
  finance: 'Hisob-kitob', profile: 'Do‘kon profili', help: 'Aloqa', logout: 'Chiqish',
  shop: 'Do‘kon', welcome: 'Do‘koningiz ish maydoni',
  welcomeCopy: 'Mahsulot buyurtma qiling va yetkazish jarayonini kuzating.',
  completeProfile: 'Do‘kon profilini to‘ldirish', firstOrder: 'Katalogni ochish',
  search: 'Mahsulot qidirish', allCompanies: 'Barcha kompaniyalar', quantity: 'Miqdor',
  addToCart: 'Savatga', emptyCatalog: 'Mahsulot topilmadi', emptyCart: 'Savat bo‘sh',
  checkout: 'Buyurtma berish', deliveryDate: 'Yetkazish sanasi',
  deliveryFrom: 'Qulay vaqt, dan', deliveryTo: 'Qulay vaqt, gacha', note: 'Izoh',
  confirmOrder: 'Buyurtmani tasdiqlash', total: 'Jami',
  cutoff: 'Ertangi buyurtmalar qabul qilinadi:', orderHistory: 'Buyurtmalar tarixi',
  repeatLastOrder: 'Oxirgi buyurtmani takrorlash',
  repeatLastLoaded: 'Oxirgi buyurtma savatga yuklandi.',
  repeatLastNone: 'Oxirgi buyurtmada faol mahsulot qolmagan.',
  repeatLastSkipped: '{count} ta nofaol mahsulot o‘tkazib yuborildi; qolganlari savatga qo‘shildi.',
  repeat: 'Oxirgi buyurtmani takrorlash', cancel: 'Buyurtmani bekor qilish',
  status: 'Holati', eta: 'Yetib borish vaqti', driver: 'Haydovchi telefoni',
  balance: 'Joriy qarz', paymentHistory: 'To‘lovlar tarixi', save: 'Saqlash',
  createProfile: 'Profilni yaratish', company: 'Kompaniya', ownerName: 'Egasi',
  phonePrimary: 'Asosiy telefon', phoneSecondary: 'Qo‘shimcha telefon',
  address: 'Manzil', district: 'Tuman', location: 'Joylashuv',
  chooseOnMap: 'Xaritada nuqtani belgilang', myLocation: 'Joylashuvim',
  emptyOrders: 'Hozircha buyurtma yo‘q', noPayments: 'Hozircha to‘lov yo‘q',
  loading: 'Yuklanmoqda…', tryAgain: 'Qayta urinish',
  gpsError: 'Joylashuvni aniqlab bo‘lmadi.', orderConfirmed: 'Buyurtma yuborildi',
  profileSaved: 'Profil saqlandi', smsNotifications: 'Buyurtma SMS xabarnomalari',
  smsNotificationsHint: 'O‘chirilganda buyurtma xabarlari kelmaydi. Kirish va tasdiqlash kodlari kelishda davom etadi.',
}

const profileSchema = z.object({
  company_id: z.string().optional(),
  name: z.string().trim().min(2, 'Do‘kon nomini kiriting.').max(200),
  owner_name: z.string().trim().min(2, 'Egasi ismini kiriting.').max(200),
  phone_primary: z.string().min(10, 'Telefon raqamini to‘liq kiriting.'),
  phone_secondary: z.string().optional(),
  address: z.string().trim().min(3, 'Manzilni kiriting.').max(500),
  district: z.string().trim().min(2, 'Tumanni kiriting.').max(120),
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  sms_notifications_enabled: z.boolean(),
})
type ProfileValues = z.infer<typeof profileSchema>

const unitLabels: Record<CatalogProduct['unit'], string> = { piece: 'dona', box: 'quti', block: 'blok' }
const statusLabels: Record<ShopOrder['status'], string> = {
  new: 'Yangi', confirmed: 'Tasdiqlandi', loaded: 'Yuklandi',
  in_transit: 'Yo‘lda', delivered: 'Yetkazildi', cancelled: 'Bekor qilindi',
}
const deliveryIssueLabels: Record<string, string> = {
  shop_closed: 'Do‘kon yopiq',
  refused: 'Qabul qilmadi',
  partial_delivery: 'Qisman yetkazildi',
  other: 'Boshqa sabab',
}

function money(value: string | number) {
  return new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 2 }).format(Number(value)) + ' so‘m'
}

function moneyInCents(value: number) {
  return Math.round(value * 100)
}

function formatPhone(value: string) {
  let digits = value.replace(/\D/g, '')
  if (digits.startsWith('998')) digits = digits.slice(3)
  digits = digits.slice(0, 9)
  const groups = [digits.slice(0, 2), digits.slice(2, 5), digits.slice(5, 7), digits.slice(7, 9)]
  return groups.filter(Boolean).join(' ')
}

function normalizePhone(value: string) {
  const digits = value.replace(/\D/g, '')
  return digits.startsWith('998') ? `+${digits}` : `+998${digits}`
}

function dateInDays(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function ShopThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  return (
    <button className="shop-icon-button" type="button" aria-label={dark ? 'Yorug‘ rejim' : 'Qorong‘i rejim'} onClick={() => setDark((value) => !value)}>
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  )
}

function LoadingRows() {
  return <div className="shop-skeletons" aria-label="Yuklanmoqda"><i /><i /><i /></div>
}

function ErrorState({ message, onRetry, t }: { message: string; onRetry: () => void; t: Copy }) {
  return <div className="shop-empty-state"><span className="shop-empty-icon"><X size={22} /></span><strong>{message}</strong><button className="shop-secondary-button" type="button" onClick={onRetry}>{t('tryAgain')}</button></div>
}

function ShopPanel() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [language, setLanguage] = useState<'uz' | 'ru'>(() => localStorage.getItem('shop-language') === 'ru' ? 'ru' : 'uz')
  const [cart, setCart] = useState<CartLine[]>([])
  const [cartCompanyId, setCartCompanyId] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const [repeatingLastOrder, setRepeatingLastOrder] = useState(false)
  const t: Copy = (key) => language === 'ru' ? ru[key] : uz[key]

  const profile = useQuery<ShopProfile | null>({
    queryKey: ['shop-profile'],
    queryFn: async () => {
      try {
        return (await api.get<ShopProfile>('/v1/shop/profile/')).data
      } catch (error) {
        if ((error as { response?: { status?: number } }).response?.status === 404) return null
        throw error
      }
    },
    retry: false,
  })

  const activeContact = profile.data?.company_contacts.find((company) => company.phone)
  const cartCount = cart.reduce((sum, item) => sum + item.quantity, 0)
  const setLocale = (value: 'uz' | 'ru') => {
    setLanguage(value)
    localStorage.setItem('shop-language', value)
  }
  const addToCart = (product: CatalogProduct) => {
    if (cartCompanyId !== null && cartCompanyId !== product.company_id) {
      setNotice('Bir savatda faqat bitta kompaniya mahsulotlari bo‘lishi mumkin. Avval savatni yakunlang yoki tozalang.')
      return
    }
    setCartCompanyId(product.company_id)
    setCart((items) => {
      const existing = items.find((item) => item.product.id === product.id)
      return existing
        ? items.map((item) => item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item)
        : [...items, { product, quantity: 1 }]
    })
    setNotice(`${product.name} savatga qo‘shildi`)
  }
  const updateCart = (productId: number, quantity: number) => {
    setCart((items) => {
      const updated = items.map((item) => item.product.id === productId ? { ...item, quantity } : item).filter((item) => item.quantity > 0)
      if (!updated.length) setCartCompanyId(null)
      return updated
    })
  }
  const clearCart = () => { setCart([]); setCartCompanyId(null) }
  const repeatLastOrder = async () => {
    setRepeatingLastOrder(true)
    try {
      const { data } = await api.get<RepeatLastOrderCart>('/v1/orders/repeat-cart/')
      const items = data.items.map(({ product, quantity }) => ({
        product,
        quantity: Number(quantity),
      }))
      setCart(items)
      setCartCompanyId(items[0]?.product.company_id ?? null)
      navigate('/shop/cart')
      setNotice(data.items.length === 0
        ? t('repeatLastNone')
        : data.omitted_count > 0
          ? t('repeatLastSkipped').replace('{count}', String(data.omitted_count))
          : t('repeatLastLoaded'))
    } catch (error) {
      setNotice(apiErrorMessage(error, 'Oxirgi buyurtmani savatga yuklab bo‘lmadi.'))
    } finally {
      setRepeatingLastOrder(false)
    }
  }
  const signOut = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const navItems = [
    { to: '/shop', key: 'home' as const, icon: Home, end: true },
    { to: '/shop/catalog', key: 'catalog' as const, icon: Package },
    { to: '/shop/cart', key: 'cart' as const, icon: ShoppingBag, count: cartCount },
    { to: '/shop/orders', key: 'orders' as const, icon: ClipboardList },
    { to: '/shop/profile', key: 'profile' as const, icon: UserRound },
  ]

  return (
    <div className="shop-app-shell">
      <aside className="shop-sidebar">
        <Link className="shop-brand" to="/shop"><span className="shop-brand-mark">t</span><span><strong>tarqatuv</strong><small>{t('shop')}</small></span></Link>
        <div className="shop-side-label">DO‘KONCHI PANELI</div>
        <nav className="shop-nav" aria-label="Asosiy navigatsiya">
          {navItems.map(({ to, key, icon: Icon, end, count }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `shop-nav-link ${isActive ? 'shop-nav-active' : ''}`}>
              <Icon size={18} strokeWidth={1.8} /><span>{t(key)}</span>{count ? <b className="shop-nav-count">{count}</b> : null}
            </NavLink>
          ))}
          <NavLink to="/shop/finance" className={({ isActive }) => `shop-nav-link ${isActive ? 'shop-nav-active' : ''}`}><Wallet size={18} strokeWidth={1.8} /><span>{t('finance')}</span></NavLink>
        </nav>
        <div className="shop-sidebar-bottom">
          <div className="shop-account"><span className="shop-account-avatar">{user?.phone.slice(-2)}</span><span><strong>{profile.data?.name || user?.phone}</strong><small>{user?.phone}</small></span></div>
          <button className="shop-logout" onClick={() => void signOut()} type="button"><ArrowLeft size={16} />{t('logout')}</button>
        </div>
      </aside>
      <main className="shop-main">
        <header className="shop-topbar">
          <div className="shop-breadcrumb">Tarqatuv <span>/</span> {t(navItems.find((item) => location.pathname === item.to || (item.to !== '/shop' && location.pathname.startsWith(item.to)))?.key ?? 'home')}</div>
          <div className="shop-top-actions">
            {activeContact?.phone ? <a className="shop-help-link" href={`tel:${activeContact.phone}`}><Phone size={16} />{t('help')}</a> : null}
            <label className="shop-language"><span className="sr-only">Til</span><select value={language} onChange={(event) => setLocale(event.target.value as 'uz' | 'ru')} aria-label="Til"><option value="uz">UZ</option><option value="ru">RU</option></select><ChevronDown size={13} /></label>
            <ShopThemeToggle />
          </div>
        </header>
        {notice && <div className="shop-toast" role="status"><Check size={16} />{notice}<button type="button" aria-label="Yopish" onClick={() => setNotice('')}><X size={15} /></button></div>}
        <div className="shop-page-content">
          <Routes>
            <Route index element={<ShopOverview profile={profile.data} profileLoading={profile.isLoading} cartCount={cartCount} t={t} />} />
            <Route path="catalog" element={<CatalogPage addToCart={addToCart} t={t} />} />
            <Route path="cart" element={<CartPage cart={cart} updateCart={updateCart} clearCart={clearCart} t={t} onOrdered={(id) => { clearCart(); navigate(`/shop/orders/${id}`) }} />} />
            <Route path="orders" element={<OrdersPage t={t} onRepeatLastOrder={() => void repeatLastOrder()} repeatingLastOrder={repeatingLastOrder} />} />
            <Route path="orders/:orderId" element={<OrderDetailPage t={t} onNotice={setNotice} />} />
            <Route path="profile" element={<ShopProfilePage t={t} />} />
            <Route path="finance" element={<FinancePage t={t} />} />
            <Route path="*" element={<Navigate to="/shop" replace />} />
          </Routes>
        </div>
        <nav className="shop-mobile-nav" aria-label="Mobil navigatsiya">
          {navItems.map(({ to, key, icon: Icon, end, count }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `shop-mobile-link ${isActive ? 'shop-mobile-active' : ''}`}>
              <span className="shop-mobile-icon"><Icon size={20} />{count ? <b>{count}</b> : null}</span><small>{t(key)}</small>
            </NavLink>
          ))}
        </nav>
      </main>
    </div>
  )
}

function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="shop-page-heading"><div><span className="shop-eyebrow">{eyebrow}</span><h1>{title}</h1>{description ? <p>{description}</p> : null}</div>{action}</div>
}

function ShopOverview({ profile, profileLoading, cartCount, t }: { profile?: ShopProfile | null; profileLoading: boolean; cartCount: number; t: Copy }) {
  const orders = useQuery({ queryKey: ['shop-orders', 'recent'], queryFn: async () => (await api.get<Page<ShopOrder>>('/v1/orders/')).data, enabled: Boolean(profile) })
  const finance = useQuery({ queryKey: ['shop-finance'], queryFn: async () => (await api.get<Finance>('/v1/shop/finance/')).data, enabled: Boolean(profile) })
  return (
    <>
      <PageHeading eyebrow="DO‘KONCHI MAYDONI" title={profile?.name || t('welcome')} description={t('welcomeCopy')} />
      {profileLoading ? <LoadingRows /> : !profile ? <section className="shop-onboarding-banner"><div className="shop-banner-icon"><MapPin size={23} /></div><div><h2>{t('completeProfile')}</h2><p>Buyurtma berishdan oldin manzil va xaritadagi nuqtani kiriting.</p></div><Link className="shop-primary-button" to="/shop/profile">Boshlash <ArrowRight size={16} /></Link></section> : (
        <section className="shop-metrics">
          <Link to="/shop/orders" className="shop-metric"><span className="shop-metric-label">Faol buyurtmalar</span><strong>{orders.data?.results.filter((order) => !['delivered', 'cancelled'].includes(order.status)).length ?? '—'}</strong><span className="shop-metric-foot"><ClipboardList size={15} />{t('orderHistory')}</span></Link>
          <Link to="/shop/cart" className="shop-metric"><span className="shop-metric-label">{t('cart')}</span><strong>{cartCount}</strong><span className="shop-metric-foot"><ShoppingBag size={15} />{t('checkout')}</span></Link>
          <Link to="/shop/finance" className="shop-metric"><span className="shop-metric-label">{t('balance')}</span><strong>{finance.data ? money(finance.data.balance) : '—'}</strong><span className="shop-metric-foot"><Wallet size={15} />{t('paymentHistory')}</span></Link>
        </section>
      )}
      {profile && <>
        <section className="shop-section-head"><div><span className="shop-eyebrow">TEZKOR BUYURTMA</span><h2>{t('catalog')}</h2></div><Link to="/shop/catalog" className="shop-text-link">Barchasini ko‘rish <ArrowRight size={15} /></Link></section>
        <CatalogPreview t={t} />
        <section className="shop-section-head"><div><span className="shop-eyebrow">OXIRGI FAOLLIK</span><h2>{t('orderHistory')}</h2></div><Link to="/shop/orders" className="shop-text-link">Tarix <ArrowRight size={15} /></Link></section>
        <OrderPreview query={orders} t={t} />
      </>}
    </>
  )
}

function CatalogPreview({ t }: { t: Copy }) {
  const query = useQuery({ queryKey: ['shop-catalog-preview'], queryFn: async () => (await api.get<Page<CatalogProduct>>('/v1/catalog/')).data })
  if (query.isLoading) return <LoadingRows />
  if (query.isError) return <ErrorState message="Katalogni yuklab bo‘lmadi" onRetry={() => void query.refetch()} t={t} />
  const products = query.data?.results.slice(0, 4) ?? []
  if (!products.length) return <div className="shop-inline-empty">Katalog hozircha bo‘sh.</div>
  return <div className="shop-product-grid shop-preview-grid">{products.map((product) => <ProductCard key={product.id} product={product} onAdd={() => undefined} compact />)}</div>
}

function ProductCard({ product, onAdd, compact = false }: { product: CatalogProduct; onAdd: () => void; compact?: boolean }) {
  return (
    <article className={`shop-product-card ${compact ? 'shop-product-compact' : ''}`}>
      <div className="shop-product-image">{product.image_url ? <img src={product.image_url} alt={product.name} /> : <Package size={32} strokeWidth={1.4} />}</div>
      <div className="shop-product-company">{product.company_name}</div>
      <h3>{product.name}</h3>
      <div className="shop-product-unit">{unitLabels[product.unit]}</div>
      <div className="shop-product-price">{money(product.unit_price)} <small>/ {unitLabels[product.unit]}</small></div>
      {Number(product.discount_percent) > 0 ? <span className="shop-discount">−{Number(product.discount_percent)}%</span> : null}
      {!compact && <button className="shop-add-button" onClick={onAdd} type="button"><Plus size={17} /> Savatga qo‘shish</button>}
    </article>
  )
}

function CatalogPage({ addToCart, t }: { addToCart: (product: CatalogProduct) => void; t: Copy }) {
  const [search, setSearch] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['shop-catalog', companyId, search, page],
    queryFn: async () => (await api.get<Page<CatalogProduct>>('/v1/catalog/', { params: { ...(companyId ? { company: companyId } : {}), search, page } })).data,
  })
  const companiesQuery = useQuery({ queryKey: ['shop-companies'], queryFn: async () => (await api.get<CompanyOption[]>('/v1/shop/companies/')).data })
  const products = query.data?.results ?? []
  const companies = companiesQuery.data ?? []
  const selectedCompany = companies.find((company) => company.id === Number(companyId))
  const hasNextPage = Boolean(query.data?.next)
  return (
    <>
      <PageHeading eyebrow="MAHSULOTLAR" title={t('catalog')} description="Kompaniya narxlari va do‘kon chegirmalari bilan." action={<span className="shop-cutoff-note">{selectedCompany ? t('cutoff') : 'Kompaniya cutoff vaqti'} <strong>{selectedCompany?.order_cutoff_time.slice(0, 5) ?? '—'}</strong></span>} />
      <div className="shop-catalog-toolbar">
        <label className="shop-search"><Search size={18} /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder={t('search')} /></label>
        <label className="shop-select-wrap"><span className="sr-only">{t('company')}</span><select value={companyId} onChange={(event) => { setCompanyId(event.target.value); setPage(1) }}><option value="">{t('allCompanies')}</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select><ChevronDown size={16} /></label>
      </div>
      {query.isLoading ? <LoadingRows /> : query.isError ? <ErrorState message="Katalogni yuklab bo‘lmadi" onRetry={() => void query.refetch()} t={t} /> : !products.length ? <div className="shop-empty-state"><span className="shop-empty-icon"><Package size={22} /></span><strong>{t('emptyCatalog')}</strong><p>Do‘kon profilingiz kompaniyaga ulanmagan bo‘lishi mumkin.</p><Link className="shop-secondary-button" to="/shop/profile">Profilni tekshirish</Link></div> : (
        <>
          <div className="shop-product-grid">{products.map((product) => <ProductCard key={product.id} product={product} onAdd={() => addToCart(product)} />)}</div>
          <div className="shop-pagination"><span>{query.data?.count ?? 0} mahsulot</span><div><button type="button" className="shop-secondary-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Oldingi</button><span>{page}</span><button type="button" className="shop-secondary-button" disabled={!hasNextPage} onClick={() => setPage((value) => value + 1)}>Keyingi</button></div></div>
        </>
      )}
    </>
  )
}

function CartPage({ cart, updateCart, clearCart, onOrdered, t }: { cart: CartLine[]; updateCart: (id: number, quantity: number) => void; clearCart: () => void; onOrdered: (id: number) => void; t: Copy }) {
  const [date, setDate] = useState(dateInDays(1))
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)
  const queryClient = useQueryClient()
  const total = cart.reduce((sum, item) => sum + moneyInCents(Number(item.product.unit_price)) * item.quantity, 0) / 100
  const company = cart[0]?.product
  const submit = async () => {
    if (!company) return
    setError('')
    try {
      const { data } = await api.post<ShopOrder>('/v1/orders/', {
        company_id: company.company_id,
        delivery_date: date,
        delivery_time_from: from || null,
        delivery_time_to: to || null,
        note,
        items: cart.map((item) => ({ product_id: item.product.id, quantity: item.quantity })),
      })
      await queryClient.invalidateQueries({ queryKey: ['shop-orders'] })
      await queryClient.invalidateQueries({ queryKey: ['shop-finance'] })
      onOrdered(data.id)
    } catch (submitError) {
      setError(apiErrorMessage(submitError, 'Buyurtma yuborilmadi. Kiritilgan ma’lumotlarni tekshiring.'))
      setConfirming(false)
    }
  }
  if (!cart.length) return <><PageHeading eyebrow="SAVAT" title={t('cart')} /><div className="shop-empty-state"><span className="shop-empty-icon"><ShoppingBag size={22} /></span><strong>{t('emptyCart')}</strong><p>Katalogdan kerakli mahsulotlarni qo‘shing.</p><Link className="shop-primary-button" to="/shop/catalog">Katalogga o‘tish <ArrowRight size={16} /></Link></div></>
  return (
    <>
      <PageHeading eyebrow="BUYURTMA TAYYORLASH" title={t('cart')} action={<button className="shop-text-button" type="button" onClick={clearCart}>Savatni tozalash</button>} />
      <div className="shop-checkout-layout">
        <section className="shop-cart-lines">
          <div className="shop-cart-company"><span>{company?.company_name}</span><small>{t('cutoff')} {company?.company_cutoff_time.slice(0, 5)}</small></div>
          {cart.map(({ product, quantity }) => <article className="shop-cart-line" key={product.id}>
            <div className="shop-cart-product-icon"><Package size={22} /></div><div className="shop-cart-product"><strong>{product.name}</strong><small>{money(product.unit_price)} / {unitLabels[product.unit]}</small></div>
            <div className="shop-stepper"><button type="button" aria-label="Kamaytirish" onClick={() => updateCart(product.id, quantity - 1)}><Minus size={15} /></button><span>{quantity}</span><button type="button" aria-label="Ko‘paytirish" onClick={() => updateCart(product.id, quantity + 1)}><Plus size={15} /></button></div>
            <strong className="shop-line-total">{money(Number(product.unit_price) * quantity)}</strong>
          </article>)}
          <div className="shop-cart-total"><span>{t('total')}</span><strong>{money(total)}</strong></div>
        </section>
        <section className="shop-delivery-form">
          <div className="shop-form-heading"><MapPin size={19} /><div><h2>Yetkazish tafsilotlari</h2><p>Sana va qulay vaqtni tanlang</p></div></div>
          <label className="shop-field">{t('deliveryDate')}<input type="date" min={dateInDays(1)} value={date} onChange={(event) => setDate(event.target.value)} /></label>
          <div className="shop-field-grid"><label className="shop-field">{t('deliveryFrom')}<input type="time" value={from} onChange={(event) => setFrom(event.target.value)} /></label><label className="shop-field">{t('deliveryTo')}<input type="time" value={to} onChange={(event) => setTo(event.target.value)} /></label></div>
          <label className="shop-field">{t('note')}<textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Yetkazish bo‘yicha qo‘shimcha ma’lumot" /></label>
          {error && <div className="shop-form-error" role="alert">{error}</div>}
          <button className="shop-primary-button shop-wide-button" type="button" onClick={() => setConfirming(true)}>{t('checkout')} <ArrowRight size={17} /></button>
          <p className="shop-cutoff-footnote">{t('cutoff')} <strong>{company?.company_cutoff_time.slice(0, 5)}</strong></p>
        </section>
      </div>
      {confirming && <div className="shop-modal-backdrop" role="presentation" onClick={() => setConfirming(false)}><section className="shop-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(event) => event.stopPropagation()}><button className="shop-modal-close" type="button" aria-label="Yopish" onClick={() => setConfirming(false)}><X size={18} /></button><span className="shop-modal-icon"><ShoppingBag size={23} /></span><h2 id="confirm-title">{t('confirmOrder')}?</h2><p>{company?.company_name} kompaniyasiga {money(total)} miqdorida buyurtma yuboriladi.</p><div className="shop-modal-actions"><button className="shop-secondary-button" type="button" onClick={() => setConfirming(false)}>Ortga</button><button className="shop-primary-button" type="button" onClick={() => void submit()}>{t('confirmOrder')} <Check size={16} /></button></div></section></div>}
    </>
  )
}

function StatusBadge({ status }: { status: ShopOrder['status'] }) {
  return <span className={`shop-status shop-status-${status}`}><i />{statusLabels[status]}</span>
}

function OrderPreview({ query, t }: { query: { data?: Page<ShopOrder>; isLoading: boolean; isError: boolean; refetch: () => unknown }; t: Copy }) {
  if (query.isLoading) return <LoadingRows />
  if (query.isError) return <div className="shop-inline-empty">Buyurtmalarni yuklab bo‘lmadi.</div>
  const orders = query.data?.results.slice(0, 3) ?? []
  if (!orders.length) return <div className="shop-inline-empty">{t('emptyOrders')}</div>
  return <div className="shop-order-list">{orders.map((order) => <Link className="shop-order-row" to={`/shop/orders/${order.id}`} key={order.id}><span className="shop-order-number">#{String(order.id).padStart(5, '0')}</span><span className="shop-order-company">{order.company_name}<small>{new Date(`${order.delivery_date}T00:00:00`).toLocaleDateString('uz-UZ')}</small></span><StatusBadge status={order.status} /><strong>{money(order.total_price)}</strong><ArrowRight size={16} /></Link>)}</div>
}

function OrdersPage({ t, onRepeatLastOrder, repeatingLastOrder }: { t: Copy; onRepeatLastOrder: () => void; repeatingLastOrder: boolean }) {
  const query = useQuery({ queryKey: ['shop-orders'], queryFn: async () => (await api.get<Page<ShopOrder>>('/v1/orders/')).data })
  return <><PageHeading eyebrow="TARIX VA KUZATUV" title={t('orderHistory')} description="Buyurtmalar holati va yetkazish ma’lumotlari." action={<div className="shop-order-actions">{query.data?.results.length ? <button className="shop-secondary-button" type="button" onClick={onRepeatLastOrder} disabled={repeatingLastOrder}><ClipboardList size={16} />{repeatingLastOrder ? t('loading') : t('repeatLastOrder')}</button> : null}<Link className="shop-primary-button" to="/shop/catalog">Yangi buyurtma <Plus size={17} /></Link></div>} />
    {query.isLoading ? <LoadingRows /> : query.isError ? <ErrorState message="Buyurtmalarni yuklab bo‘lmadi" onRetry={() => void query.refetch()} t={t} /> : !query.data?.results.length ? <div className="shop-empty-state"><span className="shop-empty-icon"><ClipboardList size={22} /></span><strong>{t('emptyOrders')}</strong><Link className="shop-primary-button" to="/shop/catalog">{t('firstOrder')} <ArrowRight size={16} /></Link></div> : <div className="shop-order-list">{query.data.results.map((order) => <Link className="shop-order-row" to={`/shop/orders/${order.id}`} key={order.id}><span className="shop-order-number">#{String(order.id).padStart(5, '0')}</span><span className="shop-order-company">{order.company_name}<small>{new Date(`${order.delivery_date}T00:00:00`).toLocaleDateString('uz-UZ')}</small></span><StatusBadge status={order.status} /><strong>{money(order.total_price)}</strong><ArrowRight size={16} /></Link>)}</div>}
  </>
}

function OrderDetailPage({ t, onNotice }: { t: Copy; onNotice: (value: string) => void }) {
  const { orderId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const query = useQuery({ queryKey: ['shop-order', orderId], queryFn: async () => (await api.get<ShopOrder>(`/v1/orders/${orderId}/`)).data, enabled: Boolean(orderId) })
  if (query.isLoading) return <><PageHeading eyebrow="BUYURTMA" title={t('loading')} /><LoadingRows /></>
  if (query.isError || !query.data) return <ErrorState message="Buyurtma topilmadi" onRetry={() => void query.refetch()} t={t} />
  const order = query.data
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['shop-order', orderId] })
    await queryClient.invalidateQueries({ queryKey: ['shop-orders'] })
  }
  const cancel = async () => {
    setError('')
    try {
      await api.post(`/v1/orders/${order.id}/cancel/`, {})
      await invalidate()
      onNotice('Buyurtma bekor qilindi')
    } catch (cancelError) {
      setError(apiErrorMessage(cancelError, 'Buyurtmani bekor qilib bo‘lmadi.'))
    }
  }
  const repeat = async () => {
    setError('')
    try {
      const { data } = await api.post<ShopOrder>(`/v1/orders/${order.id}/repeat/`, { delivery_date: dateInDays(1) })
      onNotice(t('orderConfirmed'))
      navigate(`/shop/orders/${data.id}`)
      await queryClient.invalidateQueries({ queryKey: ['shop-orders'] })
    } catch (repeatError) {
      setError(apiErrorMessage(repeatError, 'Buyurtmani takrorlab bo‘lmadi.'))
    }
  }
  return <>
    <button className="shop-back-button" type="button" onClick={() => navigate('/shop/orders')}><ArrowLeft size={16} /> {t('orderHistory')}</button>
    <PageHeading eyebrow={order.company_name} title={`Buyurtma #${String(order.id).padStart(5, '0')}`} action={<StatusBadge status={order.status} />} />
    <div className="shop-order-detail-grid">
      <section className="shop-panel-section"><div className="shop-section-title"><Package size={19} /><h2>Buyurtma tarkibi</h2></div>{order.items.map((item) => <div className="shop-detail-line" key={item.id}><span><strong>{item.product_name}</strong><small>{item.quantity} {unitLabels[item.unit]} × {money(item.unit_price)}</small></span><b>{money(item.line_total)}</b></div>)}<div className="shop-cart-total"><span>{t('total')}</span><strong>{money(order.total_price)}</strong></div></section>
      <section className="shop-panel-section"><div className="shop-section-title"><Compass size={19} /><h2>Yetkazish</h2></div><dl className="shop-order-facts"><div><dt>{t('deliveryDate')}</dt><dd>{new Date(`${order.delivery_date}T00:00:00`).toLocaleDateString('uz-UZ')}</dd></div><div><dt>Vaqt oralig‘i</dt><dd>{order.delivery_time_from && order.delivery_time_to ? `${order.delivery_time_from.slice(0, 5)}–${order.delivery_time_to.slice(0, 5)}` : 'Belgilanmagan'}</dd></div>{order.eta && <div><dt>{t('eta')}</dt><dd>{new Date(order.eta).toLocaleString('uz-UZ')}</dd></div>}{order.driver_phone && <div><dt>{t('driver')}</dt><dd><a href={`tel:${order.driver_phone}`}>{order.driver_phone}</a></dd></div>}</dl>{order.note && <p className="shop-order-note">{order.note}</p>}</section>
    </div>
    <section className="shop-panel-section shop-history-section"><div className="shop-section-title"><ClipboardList size={19} /><h2>Holatlar tarixi</h2></div><ol className="shop-status-history">{order.status_history.map((entry, index) => <li key={`${entry.status}-${entry.created_at}-${index}`}><span className="shop-history-dot" /><div><strong>{statusLabels[entry.status]}</strong><small>{new Date(entry.created_at).toLocaleString('uz-UZ')}{entry.actor_phone ? ` · ${entry.actor_phone}` : ''}</small>{entry.note && <p>{entry.note}</p>}</div></li>)}</ol></section>
    {order.delivery_issue_history.length > 0 && (
      <section className="shop-panel-section shop-history-section">
        <div className="shop-section-title"><ClipboardList size={19} /><h2>Yetkazish muammolari tarixi</h2></div>
        <ol className="shop-status-history">
          {order.delivery_issue_history.map((issue, index) => (
            <li key={`${issue.created_at}-${index}`}>
              <span className="shop-history-dot" style={{ borderColor: 'var(--red)' }} />
              <div>
                <strong>{deliveryIssueLabels[issue.reason] ?? issue.reason}</strong>
                <small>{new Date(issue.created_at).toLocaleString('uz-UZ')}</small>
                {issue.note && <p>{issue.note}</p>}
                {issue.delivered_items.length > 0 && (
                  <p>
                    Yetkazilgan miqdor:{' '}
                    {issue.delivered_items.map((row) => {
                      const item = order.items.find((line) => line.id === row.item_id)
                      return `${item?.product_name ?? `#${row.item_id}`} — ${row.quantity}`
                    }).join(', ')}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      </section>
    )}
    {error && <div className="shop-form-error" role="alert">{error}</div>}
    <div className="shop-order-actions"><button className="shop-secondary-button" type="button" onClick={() => void repeat()}><ClipboardList size={16} />{t('repeat')}</button>{order.status === 'new' && <button className="shop-danger-button" type="button" onClick={() => void cancel()}><X size={16} />{t('cancel')}</button>}</div>
  </>
}

function ShopProfilePage({ t }: { t: Copy }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [gpsError, setGpsError] = useState(false)
  const profile = useQuery<ShopProfile | null>({
    queryKey: ['shop-profile'],
    queryFn: async () => {
      try { return (await api.get<ShopProfile>('/v1/shop/profile/')).data }
      catch (queryError) {
        if ((queryError as { response?: { status?: number } }).response?.status === 404) return null
        throw queryError
      }
    },
  })
  const companies = useQuery({ queryKey: ['shop-companies'], queryFn: async () => (await api.get<CompanyOption[]>('/v1/shop/companies/')).data, enabled: profile.data === null })
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { company_id: '', name: '', owner_name: '', phone_primary: '', phone_secondary: '', address: '', district: '', latitude: 40.840000, longitude: 68.660000, sms_notifications_enabled: true },
  })
  const { register, control, handleSubmit, reset, setValue, watch, formState: { errors, isSubmitting } } = form
  const latitude = watch('latitude') || 40.840000
  const longitude = watch('longitude') || 68.660000
  useEffect(() => {
    if (profile.data) reset({
      name: profile.data.name, owner_name: profile.data.owner_name,
      phone_primary: formatPhone(profile.data.phone_primary),
      phone_secondary: profile.data.phone_secondary ? formatPhone(profile.data.phone_secondary) : '',
      address: profile.data.address, district: profile.data.district,
      latitude: Number(profile.data.latitude), longitude: Number(profile.data.longitude),
      sms_notifications_enabled: profile.data.sms_notifications_enabled,
    })
  }, [profile.data, reset])
  useEffect(() => {
    const listener = () => setGpsError(true)
    window.addEventListener('shop:gps-error', listener)
    return () => window.removeEventListener('shop:gps-error', listener)
  }, [])
  const chooseLocation = (lat: number, lng: number) => {
    setValue('latitude', lat, { shouldDirty: true, shouldValidate: true })
    setValue('longitude', lng, { shouldDirty: true, shouldValidate: true })
    setGpsError(false)
  }
  const onSubmit = handleSubmit(async (values) => {
    setError(''); setSuccess('')
    if (!profile.data && !values.company_id) { setError('Kompaniyani tanlang.'); return }
    const payload = {
      ...values,
      company_id: values.company_id ? Number(values.company_id) : undefined,
      phone_primary: normalizePhone(values.phone_primary),
      phone_secondary: values.phone_secondary ? normalizePhone(values.phone_secondary) : '',
    }
    try {
      if (profile.data) {
        const { company_id: _companyId, ...editable } = payload
        await api.patch('/v1/shop/profile/', editable)
      } else {
        await api.post('/v1/shop/profile/', payload)
      }
      await queryClient.invalidateQueries({ queryKey: ['shop-profile'] })
      await queryClient.invalidateQueries({ queryKey: ['shop-companies'] })
      await queryClient.invalidateQueries({ queryKey: ['shop-catalog'] })
      setSuccess(t('profileSaved'))
    } catch (submitError) {
      setError(apiErrorMessage(submitError, 'Profilni saqlab bo‘lmadi.'))
    }
  })
  if (profile.isLoading) return <><PageHeading eyebrow="SOZLAMALAR" title={t('profile')} /><LoadingRows /></>
  if (profile.isError) return <ErrorState message="Profil ma’lumotlarini yuklab bo‘lmadi" onRetry={() => void profile.refetch()} t={t} />
  const center: [number, number] = [Number(latitude), Number(longitude)]
  return <>
    <PageHeading eyebrow="DO‘KON MA’LUMOTLARI" title={t('profile')} description="Yetkazish manzili va aloqa ma’lumotlarini kiriting." />
    {profile.data?.company_contacts?.length ? <div className="shop-company-chips">{profile.data.company_contacts.map((company) => <span key={company.id}>{company.name}{company.phone && <a href={`tel:${company.phone}`} aria-label={`${company.name}ga qo‘ng‘iroq`}><Phone size={14} /></a>}</span>)}</div> : null}
    <form className="shop-profile-form" onSubmit={onSubmit} noValidate>
      {!profile.data && <label className="shop-field">{t('company')}<select {...register('company_id')} defaultValue=""><option value="">Kompaniyani tanlang</option>{(companies.data ?? []).map((company) => <option key={company.id} value={company.id}>{company.name} · buyurtmalar {company.order_cutoff_time.slice(0, 5)} gacha</option>)}</select>{errors.company_id && <small>{errors.company_id.message}</small>}</label>}
      <div className="shop-form-grid">
        <label className="shop-field">Do‘kon nomi<input {...register('name')} placeholder="Masalan, Guliston market" />{errors.name && <small>{errors.name.message}</small>}</label>
        <label className="shop-field">{t('ownerName')}<input {...register('owner_name')} placeholder="Ism familiya" />{errors.owner_name && <small>{errors.owner_name.message}</small>}</label>
        <label className="shop-field">{t('phonePrimary')}<Controller control={control} name="phone_primary" render={({ field }) => <input {...field} type="tel" inputMode="tel" placeholder="+998 90 123 45 67" onChange={(event) => field.onChange(formatPhone(event.target.value))} />} />{errors.phone_primary && <small>{errors.phone_primary.message}</small>}</label>
        <label className="shop-field">{t('phoneSecondary')}<Controller control={control} name="phone_secondary" render={({ field }) => <input {...field} type="tel" inputMode="tel" placeholder="Ixtiyoriy" onChange={(event) => field.onChange(formatPhone(event.target.value))} />} />{errors.phone_secondary && <small>{errors.phone_secondary.message}</small>}</label>
        <label className="shop-field shop-field-wide">{t('address')}<input {...register('address')} placeholder="Ko‘cha, uy, mo‘ljal" />{errors.address && <small>{errors.address.message}</small>}</label>
        <label className="shop-field">{t('district')}<input {...register('district')} placeholder="Masalan, Guliston" />{errors.district && <small>{errors.district.message}</small>}</label>
        <label className="shop-field">Akkaunt telefoni<input value={profile.data?.owner_phone ?? ''} readOnly /></label>
      </div>
      <div className="shop-map-heading"><div><span className="shop-eyebrow">{t('location')}</span><p>{t('chooseOnMap')}</p></div><span>{Number(latitude).toFixed(6)}, {Number(longitude).toFixed(6)}</span></div>
      {gpsError && <div className="shop-form-error" role="alert">{t('gpsError')}</div>}
      <Suspense fallback={<div className="shop-map-loading">Xarita yuklanmoqda…</div>}><LocationPicker key={profile.data?.id ?? 'new-shop'} latitude={center[0]} longitude={center[1]} onChange={chooseLocation} /></Suspense>
      {profile.data && <label className="shop-sms-toggle"><input type="checkbox" {...register('sms_notifications_enabled')} /><span><strong>{t('smsNotifications')}</strong><small>{t('smsNotificationsHint')}</small></span></label>}
      <div className="shop-coordinate-fields"><label className="shop-field">Latitude<input type="number" step="0.000001" {...register('latitude', { valueAsNumber: true })} /></label><label className="shop-field">Longitude<input type="number" step="0.000001" {...register('longitude', { valueAsNumber: true })} /></label></div>
      {error && <div className="shop-form-error" role="alert">{error}</div>}{success && <div className="shop-form-success" role="status"><Check size={16} />{success}</div>}
      <button className="shop-primary-button" type="submit" disabled={isSubmitting}>{isSubmitting ? t('loading') : profile.data ? t('save') : t('createProfile')} <ArrowRight size={16} /></button>
    </form>
  </>
}

function FinancePage({ t }: { t: Copy }) {
  const query = useQuery({ queryKey: ['shop-finance'], queryFn: async () => (await api.get<Finance>('/v1/shop/finance/')).data })
  const containerDeposit = query.data?.balances.reduce(
    (total, item) => total + Number(item.container_deposit),
    0,
  ) ?? 0
  return <><PageHeading eyebrow="HISOB-KITOB" title={t('finance')} description="Qarz balansi va qayd etilgan to‘lovlar." />
    {query.isLoading ? <LoadingRows /> : query.isError ? <ErrorState message="Hisob-kitobni yuklab bo‘lmadi" onRetry={() => void query.refetch()} t={t} /> : <>
      <section className="shop-balance-panel"><span><Wallet size={19} />Jami saldo</span><strong>{formatFinanceBalance(query.data?.balance ?? 0)}</strong><small>{query.data?.balances.map((item) => `${item.company_name}: ${formatFinanceBalance(item.balance)}`).join(' · ')}</small><small>Tara depoziti alohida: {money(containerDeposit)}</small></section>
      <section className="shop-finance-history"><div className="shop-section-head"><div><span className="shop-eyebrow">TO‘LOVLAR</span><h2>{t('paymentHistory')}</h2></div><CreditCard size={20} /></div>
        {!query.data?.payments.length ? <div className="shop-inline-empty">{t('noPayments')}</div> : query.data.payments.map((payment) => <article className="shop-payment-row" key={payment.id}><span className="shop-payment-icon"><CreditCard size={18} /></span><div><strong>{payment.company_name}</strong><small>{formatFinanceDate(payment.paid_at ?? payment.created_at)} · {payment.method}</small></div><b>{money(payment.amount)}</b></article>)}
      </section>
      <section className="shop-finance-history"><div className="shop-section-head"><div><span className="shop-eyebrow">BALANS YOZUVLARI</span><h2>Hisob-kitob tarixi</h2></div><Wallet size={20} /></div>
        {!query.data?.entries.length ? <div className="shop-inline-empty">Hozircha hisob-kitob yozuvi yo‘q</div> : query.data.entries.map((entry) => {
          const company = query.data?.balances.find((item) => item.company_id === entry.company_id)
          return <article className="shop-payment-row" key={entry.id}><span className="shop-payment-icon"><CreditCard size={18} /></span><div><strong>{company?.company_name ?? 'Kompaniya'} · {financeEntryLabel(entry)}</strong><small>{formatFinanceDate(entry.posted_at ?? entry.created_at)} · {entry.note || 'Izohsiz'}</small></div><b className={`shop-finance-entry-${entry.direction}`}>{entry.direction === 'debit' ? '+' : '−'}{formatFinanceMoney(entry.amount)}</b></article>
        })}
      </section>
    </>}
  </>
}

export default ShopPanel