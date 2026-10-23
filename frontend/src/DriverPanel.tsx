import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Check, CheckCircle2, LogOut, MapPin, Phone, Truck } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { apiErrorMessage } from './api'
import type { MapStop } from './DispatcherMap'
import { getDriverTripProgress, sortDriverStops } from './driverTripUtils'
import { useAuth } from './useAuth'
import './DispatcherPlanning.css'
import './DriverPanel.css'
import './DriverDelivery.css'

const DriverRouteMap = lazy(() => import('./DispatcherMap'))

type DriverOrder = {
  id: number
  status: string
  total_price: string
  items: Array<{ product_name: string; unit: string; quantity: string }>
}
type DriverStop = Omit<MapStop, 'order_ids'> & {
  id: number
  delivered_at: string | null
  address: string
  phone: string
  orders: DriverOrder[]
}
type DriverTrip = {
  id: number
  date: string
  vehicle_name: string
  vehicle_plate_number: string
  status: string
  stops: DriverStop[]
  picking_list: Array<{ product_name: string; unit: string; quantity: string }>
}

function localDate() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function formatEta(value: string | null | undefined) {
  if (!value) return 'Vaqt belgilanmagan'
  return new Intl.DateTimeFormat('uz-UZ', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(value))
}

function formatDeliveredAt(value: string) {
  return new Intl.DateTimeFormat('uz-UZ', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(value))
}

function tripStatusLabel(status: string) {
  if (status === 'confirmed') return 'Tasdiqlangan'
  if (status === 'in_progress') return 'Yo‘lda'
  if (status === 'completed') return 'Yakunlangan'
  return 'Rejalashtirilgan'
}

function unitLabel(unit: string) {
  const labels: Record<string, string> = { piece: 'dona', box: 'quti', block: 'blok' }
  return labels[unit] ?? unit
}

export default function DriverPanel() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [date, setDate] = useState(localDate)
  const [selectedTripId, setSelectedTripId] = useState<number | null>(null)
  const [logoutError, setLogoutError] = useState('')
  const tripsQuery = useQuery({
    queryKey: ['driver-trips', date],
    queryFn: async () => (
      await api.get<DriverTrip[]>('/v1/driver/trips/', { params: { date } })
    ).data,
  })
  const deliveryMutation = useMutation({
    mutationFn: async ({ tripId, stopId }: { tripId: number; stopId: number }) => (
      await api.post<DriverTrip>(
        `/v1/driver/trips/${tripId}/stops/${stopId}/delivered/`,
        {},
      )
    ).data,
    onSuccess: async (updatedTrip) => {
      queryClient.setQueryData<DriverTrip[]>(['driver-trips', date], (current) => (
        current?.map((trip) => trip.id === updatedTrip.id ? updatedTrip : trip)
      ))
      await queryClient.invalidateQueries({ queryKey: ['driver-trips', date] })
    },
  })
  const trips = tripsQuery.data ?? []
  const selectedTrip = trips.find((trip) => trip.id === selectedTripId) ?? trips[0] ?? null
  const orderedStops = selectedTrip ? sortDriverStops(selectedTrip.stops) : []
  const progress = getDriverTripProgress(selectedTrip?.stops ?? [])
  const mapStops = useMemo<MapStop[]>(
    () => selectedTrip?.stops.map((stop) => ({
      ...stop,
      order_ids: stop.orders.map((order) => order.id),
    })) ?? [],
    [selectedTrip],
  )

  const signOut = async () => {
    setLogoutError('')
    try {
      await logout()
      navigate('/staff/login', { replace: true })
    } catch {
      setLogoutError('Tizimdan chiqib bo‘lmadi. Qayta urinib ko‘ring.')
    }
  }

  return (
    <main className="driver-panel">
      <header className="driver-header">
        <div className="driver-brand"><span>t</span><div><strong>tarqatuv</strong><small>Haydovchi oynasi</small></div></div>
        <div className="driver-account">
          <span>{user?.phone}</span>
          <button type="button" className="driver-logout" onClick={() => void signOut()}>
            <LogOut size={17} /><span>Chiqish</span>
          </button>
        </div>
      </header>

      <div className="driver-content">
        <div className="driver-heading">
          <div><span className="driver-eyebrow">BUGUNGI ISH REJASI</span><h1>Mening reysim</h1></div>
          <label className="driver-date">
            <CalendarDays size={19} />
            <span>Reys sanasi</span>
            <input type="date" value={date} onChange={(event) => {
              setDate(event.target.value)
              setSelectedTripId(null)
            }} />
          </label>
        </div>

        {tripsQuery.isLoading ? (
          <div className="driver-state" role="status"><span className="driver-spinner" /> Reyslar yuklanmoqda…</div>
        ) : tripsQuery.isError ? (
          <div className="driver-state driver-error" role="alert">
            <strong>{apiErrorMessage(tripsQuery.error, 'Reys ma’lumotlarini yuklab bo‘lmadi.')}</strong>
            <button type="button" onClick={() => void tripsQuery.refetch()}>Qayta urinish</button>
          </div>
        ) : !trips.length ? (
          <div className="driver-state driver-empty"><Truck size={30} /><strong>Bu sana uchun reys yo‘q</strong><span>Boshqa sanani tanlang yoki dispetcher bilan bog‘laning.</span></div>
        ) : (
          <>
            {trips.length > 1 && (
              <section className="driver-trip-choices" aria-label="Mening reyslarim">
                {trips.map((trip, index) => (
                  <button
                    key={trip.id}
                    type="button"
                    className={`driver-trip-choice${selectedTrip?.id === trip.id ? ' driver-trip-choice-active' : ''}`}
                    onClick={() => setSelectedTripId(trip.id)}
                  >
                    {index + 1}-reys · {trip.vehicle_name}
                  </button>
                ))}
              </section>
            )}

            {selectedTrip && (
              <div className="driver-trip-content">
                <section className="driver-trip-summary">
                  <div className="driver-trip-vehicle"><span className="driver-icon"><Truck size={21} /></span><div><small>Biriktirilgan mashina</small><strong>{selectedTrip.vehicle_name} · {selectedTrip.vehicle_plate_number}</strong></div></div>
                  <span className={`driver-trip-status driver-trip-status-${selectedTrip.status}`}>{tripStatusLabel(selectedTrip.status)}</span>
                  <div className="driver-trip-stop-count"><strong>{selectedTrip.stops.length}</strong><span>ta do‘kon</span></div>
                </section>
                <section className="driver-trip-progress" aria-label="Reys bajarilishi">
                  <div><strong>Reys bajarilishi</strong><span>{progress.completed}/{progress.total} do‘kon</span></div>
                  <div
                    className="driver-trip-progress-track"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={progress.total}
                    aria-valuenow={progress.completed}
                    aria-label="Yetkazilgan do‘konlar"
                  >
                    <span style={{ width: `${progress.percentage}%` }} />
                  </div>
                </section>

                <section className="driver-section">
                  <div className="driver-section-heading"><div><span className="driver-eyebrow">YO‘NALISH</span><h2>Marshrut xaritasi</h2></div><MapPin size={20} /></div>
                  <Suspense fallback={<div className="driver-map-placeholder">Xarita yuklanmoqda…</div>}>
                    <DriverRouteMap stops={mapStops} />
                  </Suspense>
                </section>

                <section className="driver-section">
                  <div className="driver-section-heading"><div><span className="driver-eyebrow">KETMA-KETLIK BO‘YICHA</span><h2>Do‘konlar</h2></div><span className="driver-count">{selectedTrip.stops.length}</span></div>
                  {deliveryMutation.isError && (
                    <p className="driver-delivery-error" role="alert">
                      {apiErrorMessage(deliveryMutation.error, 'Yetkazilgan holatini saqlab bo‘lmadi.')}
                    </p>
                  )}
                  {selectedTrip.stops.length ? (
                    <ol className="driver-stop-list">
                      {orderedStops.map((stop, index) => (
                        <li key={stop.id} className={`driver-stop-card${stop.delivered_at ? ' driver-stop-card-delivered' : ''}`}>
                          <span className="driver-stop-number">{stop.sequence ?? index + 1}</span>
                          <div className="driver-stop-main">
                            <div className="driver-stop-heading"><div><h3>{stop.shop_name}</h3><span className="driver-stop-eta">Yetib borish: {formatEta(stop.eta)}</span></div></div>
                            <p className="driver-stop-address">{stop.address}</p>
                            {stop.phone && <a className="driver-call-button" href={`tel:${stop.phone}`}><Phone size={19} /> Do‘konga qo‘ng‘iroq qilish <span>{stop.phone}</span></a>}
                            <div className="driver-orders">
                              <strong>Buyurtmalar tarkibi</strong>
                              {stop.orders.length ? stop.orders.map((order) => (
                                <div key={order.id} className="driver-order">
                                  <span>Buyurtma #{order.id}</span>
                                  <ul>{order.items.map((item, itemIndex) => <li key={`${order.id}-${itemIndex}`}>{item.product_name} — {item.quantity} {unitLabel(item.unit)}</li>)}</ul>
                                </div>
                              )) : <span className="driver-muted">Buyurtma biriktirilmagan</span>}
                            </div>
                            {stop.delivered_at ? (
                              <div className="driver-stop-delivered" role="status">
                                <CheckCircle2 size={17} />
                                Yetkazildi · {formatDeliveredAt(stop.delivered_at)}
                              </div>
                            ) : (
                              <button
                                type="button"
                                className="driver-mark-delivered"
                                disabled={
                                  deliveryMutation.isPending
                                  || !['confirmed', 'in_progress'].includes(selectedTrip.status)
                                }
                                onClick={() => {
                                  if (!window.confirm(
                                    `${stop.shop_name} do‘koni${stop.orders.length ? `dagi ${stop.orders.length} ta buyurtma` : ''} yetkazilgan deb belgilansinmi?`,
                                  )) return
                                  deliveryMutation.reset()
                                  deliveryMutation.mutate({ tripId: selectedTrip.id, stopId: stop.id })
                                }}
                              >
                                <Check size={17} /> Yetkazildi deb belgilash
                              </button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  ) : <div className="driver-inline-empty">Reysga hali do‘kon qo‘shilmagan.</div>}
                </section>

                <section className="driver-section driver-loading-list">
                  <div className="driver-section-heading"><div><span className="driver-eyebrow">REYSGA TAYYORGARLIK</span><h2>Yuklash ro‘yxati</h2></div><span className="driver-count">{selectedTrip.picking_list.length}</span></div>
                  {selectedTrip.picking_list.length ? (
                    <ul>{selectedTrip.picking_list.map((item) => <li key={`${item.product_name}-${item.unit}`}><strong>{item.product_name}</strong><span>{item.quantity} {unitLabel(item.unit)}</span></li>)}</ul>
                  ) : <div className="driver-inline-empty">Yuklash ro‘yxatida mahsulot yo‘q.</div>}
                </section>
              </div>
            )}
          </>
        )}
        {logoutError && <p className="driver-logout-error" role="alert">{logoutError}</p>}
      </div>
    </main>
  )
}
