import { Boxes, CalendarDays, Printer, RotateCw } from 'lucide-react'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import { formatOrderDate } from './dispatcherUtils'

type PickingItem = {
  product_id: number
  product_name: string
  unit: 'piece' | 'box' | 'block' | string
  quantity: string
  total_weight: string | null
  total_volume: string | null
}
type PickingList = { date: string; items: PickingItem[] }

const unitLabels: Record<string, string> = {
  piece: 'dona',
  box: 'quti',
  block: 'blok',
}

function tomorrow() {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function quantity(value: string) {
  return new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 2 }).format(Number(value))
}

export default function PickingListPage() {
  const [date, setDate] = useState(tomorrow)
  const picking = useQuery({
    queryKey: ['dispatcher-picking-list', date],
    queryFn: async () => (
      await api.get<PickingList>('/v1/admin/orders/picking-list/', { params: { date } })
    ).data,
  })

  return (
    <section className="dispatcher-picking-page">
      <div className="dispatcher-page-heading dispatcher-picking-heading">
        <div>
          <span className="dispatcher-eyebrow">OMBOR VA YUKLASH</span>
          <h1>Yuklash ro‘yxati</h1>
          <p>Tanlangan sana uchun tasdiqlangan buyurtmalardagi mahsulotlar va jami miqdor.</p>
        </div>
        <div className="dispatcher-picking-actions">
          <label className="dispatcher-trip-date">
            <CalendarDays size={16} />
            <span>Sana</span>
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
          <button type="button" className="dispatcher-secondary-button dispatcher-print-button" onClick={() => window.print()}>
            <Printer size={16} /> Chop etish
          </button>
        </div>
      </div>
      {picking.isLoading ? (
        <div className="dispatcher-loading" role="status"><span /> Ro‘yxat yuklanmoqda…</div>
      ) : picking.isError ? (
        <div className="dispatcher-error-state" role="alert">
          <p>{apiErrorMessage(picking.error, 'Yuklash ro‘yxatini olib bo‘lmadi.')}</p>
          <button type="button" onClick={() => void picking.refetch()}><RotateCw size={15} /> Qayta urinish</button>
        </div>
      ) : picking.data ? (
        <section className="dispatcher-card dispatcher-picking-card">
          <div className="dispatcher-section-heading">
            <div>
              <span className="dispatcher-eyebrow">JAMI MAHSULOTLAR</span>
              <h2>{formatOrderDate(picking.data.date)}</h2>
            </div>
            <span className="dispatcher-picking-count">{picking.data.items.length} xil mahsulot</span>
          </div>
          {picking.data.items.length ? (
            <div className="dispatcher-table-scroll">
              <table className="dispatcher-orders-table dispatcher-picking-table">
                <thead>
                  <tr><th>Mahsulot</th><th>Jami miqdor</th><th>Jami og‘irlik</th><th>Jami hajm</th></tr>
                </thead>
                <tbody>
                  {picking.data.items.map((item) => (
                    <tr key={item.product_id}>
                      <td><strong>{item.product_name}</strong></td>
                      <td className="dispatcher-order-total">{quantity(item.quantity)} {unitLabels[item.unit] ?? item.unit}</td>
                      <td>{item.total_weight ? `${quantity(item.total_weight)} kg` : '—'}</td>
                      <td>{item.total_volume ? `${quantity(item.total_volume)} m³` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="dispatcher-empty"><Boxes size={22} /><strong>Yuklash uchun mahsulot yo‘q</strong><span>Bu sanada tasdiqlangan buyurtmalar topilmadi.</span></div>
          )}
          <div className="dispatcher-picking-footer">Ro‘yxatdagi miqdorlar shu sanaga yetkaziladigan buyurtmalar bo‘yicha jamlangan.</div>
        </section>
      ) : null}
    </section>
  )
}
