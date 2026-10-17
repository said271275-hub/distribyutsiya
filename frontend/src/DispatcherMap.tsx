import L from 'leaflet'
import { useEffect } from 'react'
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

export type MapStop = {
  shop_id: number
  shop_name: string
  district: string
  latitude: string | number
  longitude: string | number
  order_ids: number[]
  sequence?: number
  eta?: string | null
  eta_window_from?: string | null
  eta_window_to?: string | null
}

function FitMap({ stops }: { stops: MapStop[] }) {
  const map = useMap()
  useEffect(() => {
    if (!stops.length) return
    if (stops.length === 1) {
      map.setView([Number(stops[0].latitude), Number(stops[0].longitude)], 13)
      return
    }
    map.fitBounds(
      stops.map((stop) => [Number(stop.latitude), Number(stop.longitude)] as [number, number]),
      { padding: [32, 32], maxZoom: 13 },
    )
  }, [map, stops])
  return null
}

function numberedIcon(sequence: number, selected: boolean) {
  return L.divIcon({
    className: 'dispatcher-map-marker',
    html: `<span class="${selected ? 'is-selected' : ''}">${sequence}</span>`,
    iconSize: [32, 38],
    iconAnchor: [16, 34],
  })
}

function formatTime(value?: string | null) {
  if (!value) return 'Vaqt belgilanmagan'
  return new Intl.DateTimeFormat('uz-UZ', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(value))
}

export default function DispatcherMap({
  stops,
  selectable = false,
  selectedShopIds = [],
  onToggleStop,
}: {
  stops: MapStop[]
  selectable?: boolean
  selectedShopIds?: number[]
  onToggleStop?: (shopId: number) => void
}) {
  const center: [number, number] = stops.length
    ? [Number(stops[0].latitude), Number(stops[0].longitude)]
    : [40.8401, 68.6601]
  const line = stops.map(
    (stop) => [Number(stop.latitude), Number(stop.longitude)] as [number, number],
  )

  return (
    <div className="dispatcher-map-wrap" aria-label="Do‘konlar va reys marshruti xaritasi">
      <MapContainer center={center} zoom={10} scrollWheelZoom className="dispatcher-map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitMap stops={stops} />
        {line.length > 1 && (
          <Polyline positions={line} pathOptions={{ color: '#087f68', weight: 4, opacity: 0.85 }} />
        )}
        {stops.map((stop, index) => {
          const selected = selectedShopIds.includes(stop.shop_id)
          const label = stop.sequence ?? index + 1
          return selectable ? (
            <CircleMarker
              key={`${stop.shop_id}-${index}`}
              center={[Number(stop.latitude), Number(stop.longitude)]}
              radius={selected ? 10 : 8}
              pathOptions={{
                color: selected ? '#075b4b' : '#087f68',
                fillColor: selected ? '#25bd91' : '#ffffff',
                fillOpacity: 1,
              }}
              eventHandlers={{ click: () => onToggleStop?.(stop.shop_id) }}
            >
              <Popup>
                <strong>{stop.shop_name}</strong><br />
                {stop.district}<br />
                Buyurtmalar: {stop.order_ids.map((id) => `#${id}`).join(', ')}<br />
                <button type="button" onClick={() => onToggleStop?.(stop.shop_id)}>
                  {selected ? 'Tanlovdan olish' : 'Reysga qo‘shish'}
                </button>
              </Popup>
            </CircleMarker>
          ) : (
            <Marker
              key={`${stop.shop_id}-${index}`}
              position={[Number(stop.latitude), Number(stop.longitude)]}
              icon={numberedIcon(label, false)}
            >
              <Popup>
                <strong>{label}. {stop.shop_name}</strong><br />
                {stop.district}<br />
                {stop.eta_window_from && stop.eta_window_to
                  ? `${formatTime(stop.eta_window_from)}–${formatTime(stop.eta_window_to)}`
                  : formatTime(stop.eta)}
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>
      <div className="dispatcher-map-caption">
        {selectable ? 'Belgilarni bosing yoki ro‘yxatdan to‘xtashlarni tanlang.' : 'Yo‘nalish chizig‘i to‘xtashlar tartibini ko‘rsatadi.'}
      </div>
    </div>
  )
}
