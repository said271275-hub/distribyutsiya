import L from 'leaflet'
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import type { DispatcherShop } from './dispatcherShopUtils'

const shopIcon = L.divIcon({
  className: 'dispatcher-shop-map-pin',
  html: '<span></span>',
  iconSize: [28, 36],
  iconAnchor: [14, 34],
})

export default function DispatcherShopMap({ shop }: { shop: DispatcherShop }) {
  const position: [number, number] = [Number(shop.latitude), Number(shop.longitude)]

  return (
    <div className="dispatcher-shop-map-wrap" aria-label={`${shop.name} joylashgan xarita`}>
      <MapContainer center={position} zoom={14} scrollWheelZoom={false} className="dispatcher-shop-map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={position} icon={shopIcon}>
          <Popup><strong>{shop.name}</strong><br />{shop.address}, {shop.district}</Popup>
        </Marker>
      </MapContainer>
    </div>
  )
}
