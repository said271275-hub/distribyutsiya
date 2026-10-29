import { Archive, CalendarDays, Check, Pause, Play, Plus, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import './RecurringOrdersPage.css'

type ProductChoice = { id: number; name: string; unit: string }
type CompanyChoice = { id: number; name: string; products: ProductChoice[] }
type ScheduleItem = {
  product_id: number
  product_name: string
  unit: string
  quantity: string
  is_available: boolean
}
type Draft = {
  id: number
  schedule_id: number
  schedule_name: string
  company_name: string
  delivery_date: string
  status: 'pending' | 'confirmed' | 'cancelled' | 'expired'
  order_id: number | null
  items: ScheduleItem[]
  skipped_products: Array<{ id: number; name: string }>
}
type Schedule = {
  id: number
  company_id: number
  company_name: string
  name: string
  weekdays: number[]
  delivery_time_from: string | null
  delivery_time_to: string | null
  is_active: boolean
  is_archived: boolean
  items: ScheduleItem[]
  next_dates: string[]
}
type RecurringData = {
  schedules: Schedule[]
  drafts: Draft[]
  companies: CompanyChoice[]
}
type ItemInput = { product_id: number; quantity: string }

const weekdays = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
const unitLabels: Record<string, string> = { piece: 'dona', box: 'quti', block: 'blok' }

function dateLabel(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString('uz-UZ')
}

function unitLabel(unit: string) {
  return unitLabels[unit] ?? 'o‘lchov birligi'
}

export default function RecurringOrdersPage() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['shop-recurring-orders'],
    queryFn: async () => (await api.get<RecurringData>('/v1/shop/recurring-orders/')).data,
  })
  const recurringData = query.data ?? { schedules: [], drafts: [], companies: [] }
  const [scheduleId, setScheduleId] = useState<number | null>(null)
  const [companyId, setCompanyId] = useState('')
  const [name, setName] = useState('')
  const [selectedDays, setSelectedDays] = useState<number[]>([])
  const [items, setItems] = useState<ItemInput[]>([])
  const [productId, setProductId] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const companies = recurringData.companies
  const activeCompanyId = companyId || String(companies[0]?.id ?? '')
  const selectedCompany = companies.find((company) => company.id === Number(activeCompanyId))
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['shop-recurring-orders'] })
  const resetForm = () => {
    setScheduleId(null)
    setName('')
    setSelectedDays([])
    setItems([])
    setProductId('')
    setQuantity('1')
    setError('')
  }

  const editSchedule = (schedule: Schedule) => {
    setScheduleId(schedule.id)
    setCompanyId(String(schedule.company_id))
    setName(schedule.name)
    setSelectedDays(schedule.weekdays)
    setItems(schedule.items.map((item) => ({
      product_id: item.product_id,
      quantity: item.quantity,
    })))
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    const payload = {
      name: name.trim(),
      ...(scheduleId ? {} : { company_id: Number(activeCompanyId) }),
      weekdays: selectedDays,
      items: items.map((item) => ({
        product_id: item.product_id,
        quantity: Number(item.quantity).toFixed(2),
      })),
    }
    try {
      if (scheduleId) await api.patch(`/v1/shop/recurring-orders/${scheduleId}/`, payload)
      else await api.post('/v1/shop/recurring-orders/', payload)
      await refresh()
      resetForm()
    } catch (submitError) {
      setError(apiErrorMessage(submitError, 'Jadvalni saqlab bo‘lmadi.'))
    } finally {
      setSaving(false)
    }
  }

  const addItem = () => {
    const selectedProduct = Number(productId)
    const count = Number(quantity)
    if (!selectedProduct || !Number.isFinite(count) || count <= 0 || count > 10000) {
      setError('Mahsulot va 0 dan katta, 10000 dan oshmaydigan miqdorni tanlang.')
      return
    }
    if (items.some((item) => item.product_id === selectedProduct)) {
      setError('Bu mahsulot jadvalga avval qo‘shilgan.')
      return
    }
    setItems((current) => [...current, { product_id: selectedProduct, quantity: String(count) }])
    setProductId('')
    setQuantity('1')
    setError('')
  }

  const scheduleAction = async (id: number, action: 'pause' | 'resume' | 'archive') => {
    if (action === 'archive' && !window.confirm('Jadvalni arxivlaysizmi?')) return
    try {
      await api.post(`/v1/shop/recurring-orders/${id}/${action}/`)
      await refresh()
    } catch (actionError) {
      setError(apiErrorMessage(actionError, 'Jadval amalini bajarib bo‘lmadi.'))
    }
  }

  const draftAction = async (id: number, action: 'confirm' | 'cancel') => {
    try {
      const { data } = await api.post<Draft>(`/v1/shop/recurring-drafts/${id}/${action}/`)
      await refresh()
      if (action === 'confirm') {
        setError(data.skipped_products.length
          ? `Faol bo‘lmagan mahsulotlar o‘tkazib yuborildi: ${data.skipped_products.map((item) => item.name).join(', ')}.`
          : '')
      }
    } catch (actionError) {
      setError(apiErrorMessage(actionError, 'Qoralama amalini bajarib bo‘lmadi.'))
    }
  }

  const productName = (id: number) => selectedCompany?.products.find((product) => product.id === id)?.name
    ?? recurringData.schedules.flatMap((schedule) => schedule.items).find((item) => item.product_id === id)?.product_name
    ?? 'Mahsulot'

  if (query.isLoading) return <p className="recurring-state">Yuklanmoqda…</p>
  if (query.isError) return <div className="recurring-state" role="alert">Takroriy buyurtmalarni yuklab bo‘lmadi. <button type="button" onClick={() => void query.refetch()}>Qayta urinish</button></div>

  return (
    <div className="recurring-page">
      <header className="recurring-heading">
        <div><span className="shop-eyebrow">JADVAL ASOSIDA</span><h1>Takroriy buyurtmalar</h1><p>Jadvaldagi buyurtmalar avval qoralama bo‘ladi. Buyurtma faqat siz tasdiqlaganingizdan keyin yaratiladi.</p></div>
        <CalendarDays size={28} />
      </header>

      <form className="recurring-form" onSubmit={(event) => void submit(event)}>
        <div className="recurring-section-heading"><h2>{scheduleId ? 'Jadvalni tahrirlash' : 'Yangi jadval'}</h2></div>
        {!companies.length ? <p className="recurring-warning">Faol kompaniya bog‘lanishi yoki mahsulot topilmadi.</p> : <>
          <div className="recurring-form-grid">
            <label>Jadval nomi<input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="Masalan, haftalik suv" /></label>
            <label>Kompaniya<select value={activeCompanyId} disabled={Boolean(scheduleId)} onChange={(event) => { setCompanyId(event.target.value); setItems([]) }}>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select></label>
          </div>
          <fieldset className="recurring-days"><legend>Yetkazish kunlari</legend>{weekdays.map((day, index) => <label key={day}><input type="checkbox" checked={selectedDays.includes(index)} onChange={() => setSelectedDays((current) => current.includes(index) ? current.filter((value) => value !== index) : [...current, index].sort())} />{day}</label>)}</fieldset>
          <div className="recurring-add-row">
            <label>Mahsulot<select value={productId} onChange={(event) => setProductId(event.target.value)}><option value="">Tanlang</option>{selectedCompany?.products.map((product) => <option key={product.id} value={product.id}>{product.name} · {unitLabel(product.unit)}</option>)}</select></label>
            <label>Miqdor<input type="number" min="0.01" max="10000" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
            <button type="button" className="shop-secondary-button" onClick={addItem}><Plus size={16} />Qo‘shish</button>
          </div>
          {items.length > 0 && <ul className="recurring-item-list">{items.map((item) => <li key={item.product_id}><span>{productName(item.product_id)}</span><strong>{item.quantity}</strong><button type="button" aria-label={`${productName(item.product_id)}ni olib tashlash`} onClick={() => setItems((current) => current.filter((row) => row.product_id !== item.product_id))}><X size={15} /></button></li>)}</ul>}
        </>}
        {error && <p className="recurring-error" role="alert">{error}</p>}
        {companies.length > 0 && <div className="recurring-form-actions"><button type="submit" className="shop-primary-button" disabled={saving || !name.trim() || !selectedDays.length || !items.length}>{saving ? 'Saqlanmoqda…' : scheduleId ? 'O‘zgarishni saqlash' : 'Jadval yaratish'} <Check size={16} /></button>{scheduleId && <button type="button" className="shop-secondary-button" onClick={resetForm}>Bekor qilish</button>}</div>}
      </form>

      <section className="recurring-section">
        <div className="recurring-section-heading"><h2>Jadvallar</h2><span>{recurringData.schedules.length}</span></div>
        {!recurringData.schedules.length ? <p className="recurring-empty">Hozircha jadval yo‘q.</p> : recurringData.schedules.map((schedule) => <article className={`recurring-card ${schedule.is_archived ? 'recurring-archived' : ''}`} key={schedule.id}>
          <div className="recurring-card-header"><div><h3>{schedule.name}</h3><p>{schedule.company_name} · {schedule.weekdays.map((day) => weekdays[day]).join(', ')}</p></div><span className={`recurring-badge ${schedule.is_archived ? 'is-archived' : schedule.is_active ? 'is-active' : ''}`}>{schedule.is_archived ? 'Arxivlangan' : schedule.is_active ? 'Faol' : 'Pauzada'}</span></div>
          <ul className="recurring-item-list">{schedule.items.map((item) => <li key={item.product_id}><span>{item.product_name}{!item.is_available && <em> · faol emas</em>}</span><strong>{item.quantity} {unitLabel(item.unit)}</strong></li>)}</ul>
          {schedule.next_dates.length > 0 && <p className="recurring-next-dates"><strong>Keyingi sanalar:</strong> {schedule.next_dates.map(dateLabel).join(', ')}</p>}
          <div className="recurring-card-actions">{!schedule.is_archived && <><button type="button" className="shop-secondary-button" onClick={() => editSchedule(schedule)}>Tahrirlash</button><button type="button" className="shop-secondary-button" onClick={() => void scheduleAction(schedule.id, schedule.is_active ? 'pause' : 'resume')}>{schedule.is_active ? <Pause size={15} /> : <Play size={15} />}{schedule.is_active ? 'Pauza' : 'Davom ettirish'}</button><button type="button" className="shop-danger-button" onClick={() => void scheduleAction(schedule.id, 'archive')}><Archive size={15} />Arxivlash</button></>}</div>
        </article>)}
      </section>

      <section className="recurring-section">
        <div className="recurring-section-heading"><h2>Buyurtma qoralamalari</h2><span>{recurringData.drafts.filter((draft) => draft.status === 'pending').length} kutilmoqda</span></div>
        {!recurringData.drafts.length ? <p className="recurring-empty">Qoralama yo‘q. Yaqin yetkazish kunlari uchun qoralamalar avtomatik yaratiladi.</p> : recurringData.drafts.map((draft) => <article className="recurring-card" key={draft.id}>
          <div className="recurring-card-header"><div><h3>{draft.schedule_name} · {dateLabel(draft.delivery_date)}</h3><p>{draft.company_name} · {draft.status === 'pending' ? 'Tasdiqlang yoki bekor qiling' : draft.status === 'confirmed' ? `Tasdiqlandi · buyurtma #${draft.order_id}` : draft.status === 'expired' ? 'Muddati o‘tdi' : 'Bekor qilindi'}</p></div><span className={`recurring-badge ${draft.status === 'pending' ? 'is-active' : ''}`}>{draft.status === 'pending' ? 'Kutilmoqda' : draft.status === 'confirmed' ? 'Tasdiqlandi' : draft.status === 'expired' ? 'Muddati o‘tdi' : 'Bekor qilindi'}</span></div>
          {draft.items.length > 0 && <ul className="recurring-item-list">{draft.items.map((item) => <li key={item.product_id}><span>{item.product_name}{!item.is_available && <em> · faol emas</em>}</span><strong>{item.quantity} {unitLabel(item.unit)}</strong></li>)}</ul>}
          {draft.skipped_products.length > 0 && <p className="recurring-warning">Faol bo‘lmagan mahsulotlar o‘tkazib yuborildi: {draft.skipped_products.map((item) => item.name).join(', ')}</p>}
          {draft.status === 'pending' && <div className="recurring-card-actions"><button type="button" className="shop-primary-button" onClick={() => void draftAction(draft.id, 'confirm')}>Tasdiqlash <Check size={15} /></button><button type="button" className="shop-danger-button" onClick={() => void draftAction(draft.id, 'cancel')}>Bekor qilish <X size={15} /></button></div>}
        </article>)}
      </section>
    </div>
  )
}
