import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, MapPin, Pencil, Phone, Search, X } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import api, { apiErrorMessage } from './api'
import {
  buildShopPayload,
  filterShops,
  shopStatusLabel,
  type DispatcherShop,
  type ShopFormValues,
} from './dispatcherShopUtils'
import './DispatcherShops.css'

const DispatcherShopMap = lazy(() => import('./DispatcherShopMap'))

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }
type ShopRequest = { id: number; values: ShopFormValues }
type ShopStatusResponse = { status: DispatcherShop['status'] }
const emptyShops: DispatcherShop[] = []

const phonePattern = /^\+?[0-9\s()-]{7,20}$/
const shopFormSchema = z.object({
  name: z.string().trim().min(1, 'Do‘kon nomini kiriting.').max(200, 'Nom 200 belgidan oshmasin.'),
  phone_primary: z.string().trim().regex(phonePattern, 'Asosiy telefon raqamini to‘g‘ri kiriting.'),
  phone_secondary: z.string().trim().refine(
    (value) => value === '' || phonePattern.test(value),
    'Qo‘shimcha telefon raqamini to‘g‘ri kiriting.',
  ),
  address: z.string().trim().min(3, 'Manzilni kiriting.').max(500, 'Manzil 500 belgidan oshmasin.'),
  district: z.string().trim().min(2, 'Tumanni kiriting.').max(120, 'Tuman nomi 120 belgidan oshmasin.'),
  latitude: z.string().refine((value) => (
    value.trim() !== '' && Number.isFinite(Number(value)) &&
    Number(value) >= -90 && Number(value) <= 90
  ), 'Kenglik -90 va 90 oralig‘ida bo‘lishi kerak.'),
  longitude: z.string().refine((value) => (
    value.trim() !== '' && Number.isFinite(Number(value)) &&
    Number(value) >= -180 && Number(value) <= 180
  ), 'Uzunlik -180 va 180 oralig‘ida bo‘lishi kerak.'),
})

function formatPhone(phone: string) {
  if (!phone) return 'Kiritilmagan'
  return phone
}

export default function DispatcherShopsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [district, setDistrict] = useState('all')
  const [status, setStatus] = useState<'all' | 'active' | 'inactive'>('all')
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null)
  const [editingShop, setEditingShop] = useState<DispatcherShop | null>(null)
  const [error, setError] = useState('')
  const form = useForm<ShopFormValues>({
    resolver: zodResolver(shopFormSchema),
    defaultValues: {
      name: '',
      phone_primary: '',
      phone_secondary: '',
      address: '',
      district: '',
      latitude: '',
      longitude: '',
    },
  })
  const shops = useQuery({
    queryKey: ['dispatcher-shops'],
    queryFn: async () => (
      await api.get<Page<DispatcherShop>>('/v1/admin/shops/', { params: { page_size: 100 } })
    ).data,
  })
  const rows = shops.data?.results ?? emptyShops
  const districts = useMemo(
    () => [...new Set(rows.map((shop) => shop.district).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'uz')),
    [rows],
  )
  const filteredShops = useMemo(
    () => filterShops(rows, { search, district, status }),
    [rows, search, district, status],
  )
  const selectedShop = filteredShops.find((shop) => shop.id === selectedShopId) ??
    filteredShops[0] ?? null

  const updateShop = useMutation({
    mutationFn: async ({ id, values }: ShopRequest) => (
      await api.patch<DispatcherShop>(`/v1/admin/shops/${id}/`, buildShopPayload(values))
    ).data,
    onSuccess: async (shop) => {
      setError('')
      setSelectedShopId(shop.id)
      setEditingShop(null)
      await queryClient.invalidateQueries({ queryKey: ['dispatcher-shops'] })
    },
    onError: (failure) => setError(apiErrorMessage(failure, 'Do‘kon ma’lumotlarini saqlab bo‘lmadi. Qayta urinib ko‘ring.')),
  })

  const archiveShop = useMutation({
    mutationFn: async (shopId: number) => (
      await api.post<ShopStatusResponse>(`/v1/admin/shops/${shopId}/archive/`, {})
    ).data,
    onSuccess: async (_response, shopId) => {
      setError('')
      setSelectedShopId((current) => current === shopId ? null : current)
      await queryClient.invalidateQueries({ queryKey: ['dispatcher-shops'] })
    },
    onError: (failure) => setError(apiErrorMessage(failure, 'Do‘konni arxivlab bo‘lmadi. Qayta urinib ko‘ring.')),
  })

  const openEdit = (shop: DispatcherShop) => {
    setError('')
    setEditingShop(shop)
    form.reset({
      name: shop.name,
      phone_primary: shop.phone_primary,
      phone_secondary: shop.phone_secondary,
      address: shop.address,
      district: shop.district,
      latitude: shop.latitude,
      longitude: shop.longitude,
    })
  }
  const closeEdit = () => {
    if (updateShop.isPending) return
    setEditingShop(null)
    updateShop.reset()
  }
  const submitEdit = form.handleSubmit((values) => {
    if (!editingShop) return
    setError('')
    updateShop.mutate({ id: editingShop.id, values })
  })

  return (
    <section className="dispatcher-shops-page">
      <div className="dispatcher-page-heading">
        <div>
          <span className="dispatcher-eyebrow">DO‘KONLAR BOSHQARUVI</span>
          <h1>Do‘konlar</h1>
          <p>Kompaniyangizga ulangan do‘konlarni qidiring, ko‘ring va ma’lumotlarini boshqaring.</p>
        </div>
      </div>
      {error && <div className="dispatcher-shops-error" role="alert">{error}</div>}
      <section className="dispatcher-card dispatcher-shops-card">
        <div className="dispatcher-shops-toolbar">
          <label className="dispatcher-shops-search">
            <Search size={17} />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Do‘kon, telefon, manzil yoki tuman"
              aria-label="Do‘konlarni qidirish"
            />
            {search && <button type="button" aria-label="Qidiruvni tozalash" onClick={() => setSearch('')}><X size={15} /></button>}
          </label>
          <label className="dispatcher-shops-filter">
            <span>Tuman</span>
            <select value={district} onChange={(event) => setDistrict(event.target.value)}>
              <option value="all">Barcha tumanlar</option>
              {districts.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          <label className="dispatcher-shops-filter">
            <span>Holat</span>
            <select value={status} onChange={(event) => setStatus(event.target.value as typeof status)}>
              <option value="all">Barcha holatlar</option>
              <option value="active">Faol</option>
              <option value="inactive">Nofaol</option>
            </select>
          </label>
        </div>
        {shops.isLoading ? (
          <div className="dispatcher-loading" role="status"><span /> Do‘konlar yuklanmoqda…</div>
        ) : shops.isError ? (
          <div className="dispatcher-error-state" role="alert">
            <p>{apiErrorMessage(shops.error, 'Do‘konlarni yuklab bo‘lmadi.')}</p>
            <button type="button" onClick={() => void shops.refetch()}>Qayta urinish</button>
          </div>
        ) : filteredShops.length ? (
          <div className="dispatcher-shops-layout">
            <div className="dispatcher-shops-list" aria-label="Do‘konlar ro‘yxati">
              {filteredShops.map((shop) => (
                <button
                  key={shop.id}
                  type="button"
                  className={`dispatcher-shop-list-item ${selectedShop?.id === shop.id ? 'dispatcher-shop-list-selected' : ''}`}
                  aria-pressed={selectedShop?.id === shop.id}
                  onClick={() => setSelectedShopId(shop.id)}
                >
                  <span className="dispatcher-shop-list-icon"><MapPin size={17} /></span>
                  <span className="dispatcher-shop-list-copy">
                    <strong>{shop.name}</strong>
                    <small>{shop.district} · {shop.phone_primary}</small>
                  </span>
                  <span className={`dispatcher-status ${shop.status === 'active' ? 'dispatcher-status-confirmed' : shop.status === 'archived' ? 'dispatcher-status-cancelled' : 'dispatcher-status-new'}`}>
                    {shopStatusLabel(shop.status)}
                  </span>
                </button>
              ))}
            </div>
            {selectedShop && (
              <ShopDetails
                shop={selectedShop}
                onEdit={() => openEdit(selectedShop)}
                onArchive={() => {
                  if (!window.confirm(`“${selectedShop.name}” do‘koni kompaniyangiz ro‘yxatidan arxivlansinmi?`)) return
                  setError('')
                  archiveShop.mutate(selectedShop.id)
                }}
                archiving={archiveShop.isPending}
              />
            )}
          </div>
        ) : (
          <div className="dispatcher-empty">
            <MapPin size={22} />
            <strong>{rows.length ? 'Mos do‘kon topilmadi' : 'Do‘konlar topilmadi'}</strong>
            <span>{rows.length ? 'Qidiruv yoki filtrlarni o‘zgartirib ko‘ring.' : 'Kompaniyangizga ulangan faol do‘konlar yo‘q.'}</span>
          </div>
        )}
        {shops.data && <footer className="dispatcher-shops-footer">{filteredShops.length} / {shops.data.count} ta do‘kon</footer>}
      </section>

      {editingShop && (
        <div className="dispatcher-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeEdit()
        }}>
          <form
            className="dispatcher-confirm-dialog dispatcher-shop-edit-form"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dispatcher-shop-edit-title"
            onSubmit={(event) => void submitEdit(event)}
          >
            <div className="dispatcher-shop-edit-heading">
              <h2 id="dispatcher-shop-edit-title">Do‘kon ma’lumotlarini tahrirlash</h2>
              <button type="button" aria-label="Oynani yopish" onClick={closeEdit}><X size={17} /></button>
            </div>
            <label><span>Do‘kon nomi</span><input {...form.register('name')} maxLength={200} />{form.formState.errors.name && <small role="alert">{form.formState.errors.name.message}</small>}</label>
            <div className="dispatcher-shop-edit-grid">
              <label><span>Asosiy telefon</span><input {...form.register('phone_primary')} type="tel" />{form.formState.errors.phone_primary && <small role="alert">{form.formState.errors.phone_primary.message}</small>}</label>
              <label><span>Qo‘shimcha telefon</span><input {...form.register('phone_secondary')} type="tel" />{form.formState.errors.phone_secondary && <small role="alert">{form.formState.errors.phone_secondary.message}</small>}</label>
              <label><span>Tuman</span><input {...form.register('district')} maxLength={120} />{form.formState.errors.district && <small role="alert">{form.formState.errors.district.message}</small>}</label>
              <label className="dispatcher-shop-address-field"><span>Manzil</span><input {...form.register('address')} maxLength={500} />{form.formState.errors.address && <small role="alert">{form.formState.errors.address.message}</small>}</label>
              <label><span>Kenglik</span><input {...form.register('latitude')} type="number" step="0.000001" />{form.formState.errors.latitude && <small role="alert">{form.formState.errors.latitude.message}</small>}</label>
              <label><span>Uzunlik</span><input {...form.register('longitude')} type="number" step="0.000001" />{form.formState.errors.longitude && <small role="alert">{form.formState.errors.longitude.message}</small>}</label>
            </div>
            {updateShop.isError && <p className="dispatcher-shop-form-error" role="alert">{apiErrorMessage(updateShop.error, 'Do‘konni saqlab bo‘lmadi.')}</p>}
            <div className="dispatcher-dialog-actions">
              <button type="button" className="dispatcher-order-action" disabled={updateShop.isPending} onClick={closeEdit}>Bekor qilish</button>
              <button type="submit" className="dispatcher-primary-button" disabled={updateShop.isPending}>
                {updateShop.isPending ? 'Saqlanmoqda…' : 'Saqlash'}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}

function ShopDetails({
  shop,
  onEdit,
  onArchive,
  archiving,
}: {
  shop: DispatcherShop
  onEdit: () => void
  onArchive: () => void
  archiving: boolean
}) {
  return (
    <article className="dispatcher-shop-details">
      <div className="dispatcher-shop-detail-heading">
        <div>
          <span className="dispatcher-eyebrow">DO‘KON TAFSILOTI</span>
          <h2>{shop.name}</h2>
        </div>
        <span className={`dispatcher-status ${shop.status === 'active' ? 'dispatcher-status-confirmed' : shop.status === 'archived' ? 'dispatcher-status-cancelled' : 'dispatcher-status-new'}`}>
          {shopStatusLabel(shop.status)}
        </span>
      </div>
      <dl className="dispatcher-shop-contact-list">
        <div><dt><Phone size={14} /> Asosiy telefon</dt><dd>{formatPhone(shop.phone_primary)}</dd></div>
        <div><dt><Phone size={14} /> Qo‘shimcha telefon</dt><dd>{formatPhone(shop.phone_secondary)}</dd></div>
        <div><dt><MapPin size={14} /> Manzil</dt><dd>{shop.address}, {shop.district}</dd></div>
      </dl>
      <div className="dispatcher-shop-coordinates">{Number(shop.latitude).toFixed(6)}, {Number(shop.longitude).toFixed(6)}</div>
      <Suspense fallback={<div className="dispatcher-loading dispatcher-shop-map-loading" role="status"><span /> Xarita yuklanmoqda…</div>}>
        <DispatcherShopMap shop={shop} />
      </Suspense>
      <div className="dispatcher-shop-detail-actions">
        <button type="button" className="dispatcher-order-action" onClick={onEdit}><Pencil size={14} /> Tahrirlash</button>
        {shop.status !== 'archived' && (
          <button type="button" className="dispatcher-order-action dispatcher-order-cancel" disabled={archiving} onClick={onArchive}>
            <Archive size={14} /> {archiving ? 'Arxivlanmoqda…' : 'Arxivlash'}
          </button>
        )}
      </div>
    </article>
  )
}
