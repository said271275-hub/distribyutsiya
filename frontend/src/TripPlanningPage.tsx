import {
  AlertTriangle,
  CalendarDays,
  Check,
  ChevronRight,
  LoaderCircle,
  MapPin,
  Route as RouteIcon,
  Truck,
} from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import {
  formatOrderDate,
  getSuggestionLoad,
  type OrderStatus,
} from './dispatcherUtils'
import type { MapStop } from './DispatcherMap'

const DispatcherMap = lazy(() => import('./DispatcherMap'))

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }
type Order = {
  id: number
  shop_id: number
  shop_name: string
  status: OrderStatus
  delivery_date: string
  total_price: string
}
type Vehicle = {
  id: number
  name: string
  capacity: string
  is_active: boolean
  is_archived: boolean
}
type Driver = {
  id: number
  phone: string
  is_active: boolean
  blocked: boolean
}
type TripStopProposal = MapStop & {
  estimated_weight: string | null
  estimated_volume: string | null
  capacity_metric: string
  capacity_load: string | null
}
type TripProposal = {
  district: string
  vehicle_id: number
  driver_id: number
  vehicle_capacity: string
  capacity_metric: string
  estimated_load: string | null
  capacity_exceeded: boolean
  split_for_capacity: boolean
  warning: string | null
  stops: TripStopProposal[]
  order_ids: number[]
}
type SuggestionResponse = {
  date: string
  trips: TripProposal[]
  unassigned_order_ids: number[]
  unassigned_orders: Array<{ order_id: number; reason: string }>
}
type Trip = {
  id: number
  date: string
  vehicle_id: number
  vehicle_name: string
  vehicle_capacity: string
  driver_id: number
  driver_phone: string
  status: string
  routing_source: string
  stops: MapStop[]
}

function tomorrow() {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const activeTripStatuses = new Set(['planned', 'confirmed', 'in_progress'])

export default function TripPlanningPage() {
  const queryClient = useQueryClient()
  const [date, setDate] = useState(tomorrow)
  const [suggestions, setSuggestions] = useState<SuggestionResponse | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [selectedShopIds, setSelectedShopIds] = useState<number[]>([])
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null)
  const [selectedDriverId, setSelectedDriverId] = useState<number | null>(null)
  const [partialTripId, setPartialTripId] = useState<number | null>(null)
  const [savedTrip, setSavedTrip] = useState<Trip | null>(null)
  const [confirmReason, setConfirmReason] = useState('Reys dispetcher tomonidan tasdiqlandi')

  const ordersQuery = useQuery({
    queryKey: ['dispatcher-trip-orders', date],
    queryFn: async () => (
      await api.get<Page<Order>>('/v1/admin/orders/', {
        params: { date, status: 'confirmed', page_size: 100 },
      })
    ).data,
  })
  const vehiclesQuery = useQuery({
    queryKey: ['dispatcher-trip-vehicles'],
    queryFn: async () => (await api.get<Page<Vehicle>>('/v1/admin/vehicles/', { params: { page_size: 100 } })).data,
  })
  const driversQuery = useQuery({
    queryKey: ['dispatcher-trip-drivers'],
    queryFn: async () => (await api.get<Page<Driver>>('/v1/admin/drivers/', { params: { page_size: 100 } })).data,
  })
  const tripsQuery = useQuery({
    queryKey: ['dispatcher-trips', date],
    queryFn: async () => (await api.get<Page<Trip>>('/v1/admin/trips/', { params: { page_size: 100 } })).data,
  })

  const occupiedVehicles = useMemo(
    () => new Set((tripsQuery.data?.results ?? [])
      .filter((trip) => trip.date === date && activeTripStatuses.has(trip.status))
      .map((trip) => trip.vehicle_id)),
    [date, tripsQuery.data],
  )
  const occupiedDrivers = useMemo(
    () => new Set((tripsQuery.data?.results ?? [])
      .filter((trip) => trip.date === date && activeTripStatuses.has(trip.status))
      .map((trip) => trip.driver_id)),
    [date, tripsQuery.data],
  )
  const vehicles = (vehiclesQuery.data?.results ?? []).filter(
    (vehicle) => vehicle.is_active && !vehicle.is_archived && !occupiedVehicles.has(vehicle.id),
  )
  const drivers = (driversQuery.data?.results ?? []).filter(
    (driver) => driver.is_active && !driver.blocked && !occupiedDrivers.has(driver.id),
  )
  const availableVehicleIds = vehicles.map((vehicle) => vehicle.id)
  const selectedProposal = suggestions?.trips[selectedIndex] ?? null
  const proposalStops = selectedProposal?.stops ?? []
  const selectedStops = proposalStops.filter((stop) => selectedShopIds.includes(stop.shop_id))
  const load = getSuggestionLoad(selectedStops)
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === selectedVehicleId)
  const loadExceedsCapacity = Boolean(
    selectedVehicle &&
    load.load !== null &&
    load.load > Number(selectedVehicle.capacity),
  )
  const orderById = new Map((ordersQuery.data?.results ?? []).map((order) => [order.id, order]))

  const suggestionMutation = useMutation({
    mutationFn: async () => (
      await api.post<SuggestionResponse>('/v1/admin/trips/suggest/', {
        date,
        vehicle_ids: availableVehicleIds,
      })
    ).data,
    onSuccess: (data) => {
      setSuggestions(data)
      setSelectedIndex(0)
      const firstProposal = data.trips[0]
      setSelectedShopIds(firstProposal?.stops.map((stop) => stop.shop_id) ?? [])
      setSelectedVehicleId(firstProposal?.vehicle_id ?? null)
      setSelectedDriverId(firstProposal?.driver_id ?? null)
      setSavedTrip(null)
      setPartialTripId(null)
    },
  })

  const createTripMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProposal || !selectedVehicleId || !selectedDriverId || !selectedStops.length) {
        throw new Error('Reys uchun nuqta, mashina va haydovchini tanlang.')
      }
      let tripId = partialTripId
      if (tripId === null) {
        const created = await api.post<Trip>('/v1/admin/trips/', {
          date,
          vehicle_id: selectedVehicleId,
          driver_id: selectedDriverId,
        })
        tripId = created.data.id
        setPartialTripId(tripId)
      }
      for (const stop of selectedStops) {
        await api.post(`/v1/admin/trips/${tripId}/stops/`, {
          shop_id: stop.shop_id,
          order_ids: stop.order_ids,
        })
      }
      const routed = await api.post<Trip>(`/v1/admin/trips/${tripId}/route/`, {})
      return routed.data
    },
    onSuccess: async (trip) => {
      setSavedTrip(trip)
      setPartialTripId(null)
      setSuggestions(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dispatcher-trips'] }),
        queryClient.invalidateQueries({ queryKey: ['dispatcher-trip-orders'] }),
        queryClient.invalidateQueries({ queryKey: ['dispatcher-dashboard'] }),
      ])
    },
  })

  const confirmTripMutation = useMutation({
    mutationFn: async () => {
      if (!savedTrip) throw new Error('Avval reysni saqlang.')
      const response = await api.post<Trip>(`/v1/admin/trips/${savedTrip.id}/confirm/`, {
        reason: confirmReason,
      })
      return response.data
    },
    onSuccess: async (trip) => {
      setSavedTrip(trip)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dispatcher-trips'] }),
        queryClient.invalidateQueries({ queryKey: ['dispatcher-dashboard'] }),
      ])
    },
  })

  const pageError = [ordersQuery, vehiclesQuery, driversQuery, tripsQuery].find((query) => query.isError)
  const toggleStop = (shopId: number) => {
    setSelectedShopIds((current) => current.includes(shopId)
      ? current.filter((id) => id !== shopId)
      : [...current, shopId])
    setSavedTrip(null)
  }
  const apiError = suggestionMutation.error ?? createTripMutation.error ?? confirmTripMutation.error

  return (
    <section className="dispatcher-trip-page">
      <div className="dispatcher-page-heading">
        <div>
          <span className="dispatcher-eyebrow">BUYURTMALARDAN REYSGACHA</span>
          <h1>Reys tuzish</h1>
          <p>Tasdiqlangan buyurtmalarni ko‘rib, xaritada to‘xtashlarni tanlang va reysni shakllantiring.</p>
        </div>
        <label className="dispatcher-trip-date">
          <CalendarDays size={16} />
          <span>Yetkazish sanasi</span>
          <input type="date" value={date} onChange={(event) => {
            setDate(event.target.value)
            setSuggestions(null)
            setSavedTrip(null)
          }} />
        </label>
      </div>

      <div className="dispatcher-trip-toolbar">
        <button
          type="button"
          className="dispatcher-primary-button"
          disabled={suggestionMutation.isPending || ordersQuery.isLoading || vehiclesQuery.isLoading || driversQuery.isLoading || tripsQuery.isLoading}
          onClick={() => suggestionMutation.mutate()}
        >
          {suggestionMutation.isPending ? <LoaderCircle className="dispatcher-spinning" size={16} /> : <RouteIcon size={16} />}
          Avtomatik guruhlash taklifini olish
        </button>
        <span>{ordersQuery.data?.count ?? 0} ta tasdiqlangan buyurtma</span>
        <span>{vehicles.length} ta mashina, {drivers.length} ta haydovchi bo‘sh</span>
      </div>

      {pageError && <div className="dispatcher-inline-alert" role="alert">{apiErrorMessage(pageError.error, 'Kerakli ma’lumotlarni yuklab bo‘lmadi.')}</div>}
      {apiError && <div className="dispatcher-inline-alert" role="alert">{apiErrorMessage(apiError, 'Amalni bajarib bo‘lmadi.')}</div>}
      {suggestionMutation.isSuccess && suggestions?.trips.length === 0 && suggestions.unassigned_orders.length === 0 && (
        <div className="dispatcher-inline-empty">Bu sana uchun reysga biriktirilmagan tasdiqlangan buyurtmalar yo‘q.</div>
      )}

      {suggestions && (
        <div className="dispatcher-planning-grid">
          <section className="dispatcher-card dispatcher-proposals">
            <div className="dispatcher-section-heading">
              <div><span className="dispatcher-eyebrow">TIZIM TAKLIFI</span><h2>Taklif qilingan reyslar</h2></div>
              <span className="dispatcher-proposal-count">{suggestions.trips.length}</span>
            </div>
            {suggestions.trips.length ? (
              <div className="dispatcher-proposal-list">
                {suggestions.trips.map((proposal, index) => (
                  <button
                    type="button"
                    key={`${proposal.vehicle_id}-${proposal.driver_id}-${index}`}
                    className={`dispatcher-proposal ${selectedIndex === index ? 'dispatcher-proposal-active' : ''}`}
                    onClick={() => {
                      setSelectedIndex(index)
                      setSelectedShopIds(proposal.stops.map((stop) => stop.shop_id))
                      setSelectedVehicleId(proposal.vehicle_id)
                      setSelectedDriverId(proposal.driver_id)
                      setSavedTrip(null)
                    }}
                  >
                    <span><strong>{proposal.district}</strong><small>{proposal.stops.length} ta to‘xtash · {proposal.order_ids.length} ta buyurtma</small></span>
                    <span className="dispatcher-proposal-end"><b>#{proposal.vehicle_id}</b><ChevronRight size={16} /></span>
                    {proposal.warning && <small className="dispatcher-proposal-warning"><AlertTriangle size={13} />{proposal.warning}</small>}
                  </button>
                ))}
              </div>
            ) : (
              <div className="dispatcher-inline-empty">Bo‘sh mashina va haydovchiga mos reys taklifi yo‘q.</div>
            )}
            {suggestions.unassigned_orders.length > 0 && (
              <div className="dispatcher-unassigned" role="status">
                <div><AlertTriangle size={16} /><strong>Taqsimlanmagan buyurtmalar</strong></div>
                {suggestions.unassigned_orders.map(({ order_id, reason }) => (
                  <p key={order_id}>
                    <b>#{order_id}</b> {orderById.get(order_id)?.shop_name ?? ''}
                    <small>{reason}</small>
                  </p>
                ))}
              </div>
            )}
          </section>

          {selectedProposal && (
            <section className="dispatcher-card dispatcher-proposal-detail">
              <div className="dispatcher-section-heading">
                <div><span className="dispatcher-eyebrow">REYS {selectedIndex + 1}</span><h2>{selectedProposal.district}</h2></div>
                <MapPin size={19} />
              </div>
              <div className="dispatcher-assignment-fields">
                <label>
                  <span>Mashina</span>
                  <select value={selectedVehicleId ?? ''} onChange={(event) => setSelectedVehicleId(Number(event.target.value) || null)}>
                    {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.name} · sig‘im {vehicle.capacity}</option>)}
                  </select>
                </label>
                <label>
                  <span>Haydovchi</span>
                  <select value={selectedDriverId ?? ''} onChange={(event) => setSelectedDriverId(Number(event.target.value) || null)}>
                    {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.phone}</option>)}
                  </select>
                </label>
              </div>
              <div className="dispatcher-stop-selection">
                <div className="dispatcher-selection-heading"><strong>To‘xtash nuqtalari</strong><span>{selectedStops.length}/{proposalStops.length} tanlandi</span></div>
                {proposalStops.map((stop, index) => {
                  const checked = selectedShopIds.includes(stop.shop_id)
                  return (
                    <label className="dispatcher-stop-option" key={stop.shop_id}>
                      <input type="checkbox" checked={checked} onChange={() => toggleStop(stop.shop_id)} />
                      <span className="dispatcher-stop-number">{index + 1}</span>
                      <span className="dispatcher-stop-name"><strong>{stop.shop_name}</strong><small>{stop.district} · {stop.order_ids.map((id) => `#${id}`).join(', ')}</small></span>
                      <span className="dispatcher-stop-load">{stop.capacity_load ?? '—'} {stop.capacity_metric === 'weight' ? 'kg' : stop.capacity_metric === 'volume' ? 'm³' : ''}</span>
                    </label>
                  )
                })}
              </div>
              <div className={`dispatcher-capacity ${loadExceedsCapacity || selectedProposal.capacity_exceeded ? 'dispatcher-capacity-warning' : ''}`}>
                <Truck size={16} />
                {load.load === null
                  ? 'Tanlangan yukning sig‘imi noma’lum'
                  : `Jami yuk: ${load.load.toFixed(3)} ${load.metric === 'weight' ? 'kg' : 'm³'} / ${selectedVehicle?.capacity ?? selectedProposal.vehicle_capacity}`}
                {(loadExceedsCapacity || (selectedStops.length === proposalStops.length && selectedProposal.capacity_exceeded)) && <strong><AlertTriangle size={14} /> Mashina sig‘imidan oshdi</strong>}
              </div>
              <Suspense fallback={<div className="dispatcher-loading">Xarita yuklanmoqda…</div>}>
                <DispatcherMap
                  stops={proposalStops}
                  selectable
                  selectedShopIds={selectedShopIds}
                  onToggleStop={toggleStop}
                />
              </Suspense>
              <button
                type="button"
                className="dispatcher-primary-button dispatcher-create-trip"
                disabled={createTripMutation.isPending || !selectedVehicleId || !selectedDriverId || !selectedStops.length || Boolean(savedTrip)}
                onClick={() => createTripMutation.mutate()}
              >
                {createTripMutation.isPending ? <LoaderCircle className="dispatcher-spinning" size={16} /> : <Check size={16} />}
                {partialTripId ? 'Reysni davom ettirish' : 'Tanlangan nuqtalardan reys yaratish'}
              </button>
            </section>
          )}
        </div>
      )}

      {savedTrip && (
        <section className="dispatcher-card dispatcher-saved-trip">
          <div className="dispatcher-section-heading">
            <div><span className="dispatcher-eyebrow">REYS #{savedTrip.id}</span><h2>Marshrut va yetib borish vaqti</h2></div>
            <span className={`dispatcher-status dispatcher-status-${savedTrip.status}`}>{savedTrip.status === 'confirmed' ? 'Tasdiqlangan' : 'Rejalashtirilgan'}</span>
          </div>
          <div className="dispatcher-saved-trip-meta">
            <span><Truck size={15} />{savedTrip.vehicle_name}</span>
            <span>Haydovchi: {savedTrip.driver_phone}</span>
            <span>Yo‘nalish: {savedTrip.routing_source === 'osrm' ? 'OSRM' : 'zaxira hisob'}</span>
          </div>
          <Suspense fallback={<div className="dispatcher-loading">Xarita yuklanmoqda…</div>}>
            <DispatcherMap stops={savedTrip.stops} />
          </Suspense>
          <ol className="dispatcher-route-list">
            {savedTrip.stops.map((stop) => (
              <li key={stop.shop_id}>
                <span className="dispatcher-route-stop-number">{stop.sequence}</span>
                <span><strong>{stop.shop_name}</strong><small>{stop.district} · {stop.order_ids.map((id) => `#${id}`).join(', ')}</small></span>
                <span className="dispatcher-route-eta">{stop.eta_window_from && stop.eta_window_to
                  ? `${formatOrderDate(stop.eta_window_from.slice(0, 10))} · ${new Date(stop.eta_window_from).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tashkent' })}–${new Date(stop.eta_window_to).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Tashkent' })}`
                  : 'Vaqt belgilanmagan'}</span>
              </li>
            ))}
          </ol>
          {savedTrip.status !== 'confirmed' && (
            <div className="dispatcher-confirm-trip">
              <label><span>Tasdiqlash sababi</span><input value={confirmReason} onChange={(event) => setConfirmReason(event.target.value)} /></label>
              <button type="button" className="dispatcher-primary-button" disabled={confirmTripMutation.isPending || !confirmReason.trim()} onClick={() => confirmTripMutation.mutate()}>
                {confirmTripMutation.isPending ? <LoaderCircle className="dispatcher-spinning" size={16} /> : <Check size={16} />}
                Reysni tasdiqlash
              </button>
            </div>
          )}
        </section>
      )}
    </section>
  )
}
