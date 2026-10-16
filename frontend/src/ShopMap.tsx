import L from 'leaflet'
import { useEffect } from 'react'
import { Compass } from 'lucide-react'
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

function MapClickHandler({ onChange }: { onChange: (lat: number, lng: number) => void }) {
  useMapEvents({ click(event) { onChange(Number(event.latlng.lat.toFixed(6)), Number(event.latlng.lng.toFixed(6))) } })
  return null
}

function MovingMarker({ latitude, longitude }: { latitude: number; longitude: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView([latitude, longitude], map.getZoom())
  }, [latitude, longitude, map])
  return <Marker position={[latitude, longitude]} icon={locationPin} />
}

const locationPin = L.divIcon({ className: 'shop-map-pin', html: '<span></span>', iconSize: [28, 36], iconAnchor: [14, 34] })

export default function ShopMap({ latitude, longitude, onChange }: {
  latitude: number
  longitude: number
  onChange: (lat: number, lng: number) => void
}) {
  const gps = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => onChange(Number(coords.latitude.toFixed(6)), Number(coords.longitude.toFixed(6))),
      () => window.dispatchEvent(new CustomEvent('shop:gps-error')),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }
  return <div className="shop-map-wrap"><MapContainer center={[latitude, longitude]} zoom={14} scrollWheelZoom={false} className="shop-map">
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    <MapClickHandler onChange={onChange} /><MovingMarker latitude={latitude} longitude={longitude} />
  </MapContainer><button className="shop-gps-button" type="button" onClick={gps}><Compass size={16} /> Joylashuvim</button></div>
}