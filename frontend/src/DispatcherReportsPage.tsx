import { Download, FileText } from 'lucide-react'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api, { apiErrorMessage } from './api'
import { formatCurrency } from './dispatcherUtils'
import './DispatcherReports.css'

type ReportName = 'sales' | 'debtors' | 'drivers' | 'products'
type SalesRow = {
  date: string
  delivered_orders: number
  delivered_amount: string
  cancelled_orders: number
  problem_orders: number
}
type DebtorRow = {
  shop_id: number
  shop_name: string
  current_balance: string
  last_payment_date: string | null
}
type DriverRow = {
  driver_id: number
  driver_phone: string
  trips: number
  delivered_shops: number
  problem_shops: number
  reasons: Record<string, { label: string; count: number }>
}
type ProductRow = {
  product_id: number
  product_name: string
  unit: string
  delivered_quantity: string
  delivered_amount: string
}
type ReportData = {
  report: ReportName
  start_date: string
  end_date: string
  summary: Record<string, number | string>
  rows?: SalesRow[] | DriverRow[] | ProductRow[]
  debtors?: DebtorRow[]
  prepaid?: DebtorRow[]
}

const reports: Array<{ id: ReportName; label: string }> = [
  { id: 'sales', label: 'Savdo' },
  { id: 'debtors', label: 'Qarzdorlar' },
  { id: 'drivers', label: 'Haydovchilar' },
  { id: 'products', label: 'Mahsulotlar' },
]

function localDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function dateLabel(value: string | null) {
  if (!value) return 'To‘lov qayd etilmagan'
  return new Date(`${value}T00:00:00`).toLocaleDateString('uz-UZ')
}

function money(value: string | number | undefined) {
  return formatCurrency(Number(value ?? 0))
}

export default function DispatcherReportsPage() {
  const [report, setReport] = useState<ReportName>('sales')
  const [period, setPeriod] = useState('7')
  const [presetDates] = useState(() => {
    const today = new Date()
    const end = localDate(today)
    const startFor = (days: number) => {
      const start = new Date(today)
      start.setDate(start.getDate() - (days - 1))
      return localDate(start)
    }
    return {
      '1': { start: end, end },
      '7': { start: startFor(7), end },
      '30': { start: startFor(30), end },
    }
  })
  const [startDate, setStartDate] = useState(presetDates['7'].start)
  const [endDate, setEndDate] = useState(presetDates['7'].end)
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState(false)
  const query = useQuery({
    queryKey: ['dispatcher-reports', report, startDate, endDate],
    queryFn: async () => {
      const { data } = await api.get<ReportData>('/v1/admin/reports/', {
        params: { report, start_date: startDate, end_date: endDate },
      })
      return data
    },
  })

  const selectPeriod = (value: string) => {
    setPeriod(value)
    if (value === 'custom') return
    const preset = presetDates[value as keyof typeof presetDates]
    if (preset) {
      setStartDate(preset.start)
      setEndDate(preset.end)
    }
  }

  const exportCsv = async () => {
    setExportError('')
    setExporting(true)
    try {
      const response = await api.get<Blob>('/v1/admin/reports/', {
        params: {
          report,
          start_date: startDate,
          end_date: endDate,
          export: 'csv',
        },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${report}_${startDate}_${endDate}.csv`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      setExportError(apiErrorMessage(error, 'CSV faylini yuklab bo‘lmadi.'))
    } finally {
      setExporting(false)
    }
  }

  const data = query.data
  const summary = data?.summary ?? {}
  const title = reports.find((item) => item.id === report)?.label ?? 'Hisobot'

  return (
    <section className="dispatcher-reports-page">
      <div className="dispatcher-page-heading">
        <div>
          <span className="dispatcher-eyebrow">TAHLIL</span>
          <h1>Hisobotlar</h1>
          <p>Yetkazilgan savdo, qarzdorlik, haydovchi va mahsulot ko‘rsatkichlarini ko‘ring.</p>
        </div>
        <button
          type="button"
          className="dispatcher-report-export"
          onClick={() => void exportCsv()}
          disabled={exporting || query.isLoading}
        >
          <Download size={16} /> {exporting ? 'Tayyorlanmoqda…' : 'CSV yuklab olish'}
        </button>
      </div>

      <section className="dispatcher-card dispatcher-report-controls">
        <div className="dispatcher-report-tabs" role="tablist" aria-label="Hisobot turi">
          {reports.map((item) => (
            <button
              type="button"
              role="tab"
              aria-selected={report === item.id}
              key={item.id}
              className={report === item.id ? 'dispatcher-report-tab dispatcher-report-tab-active' : 'dispatcher-report-tab'}
              onClick={() => setReport(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="dispatcher-report-date-controls">
          <div className="dispatcher-report-periods" aria-label="Sana oralig‘i">
            {[['1', 'Bugun'], ['7', '7 kun'], ['30', '30 kun'], ['custom', 'Tanlangan']].map(([value, label]) => (
              <button
                type="button"
                key={value}
                className={period === value ? 'dispatcher-report-period dispatcher-report-period-active' : 'dispatcher-report-period'}
                onClick={() => selectPeriod(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label>
            Boshlanish sanasi
            <input
              type="date"
              value={startDate}
              max={endDate}
              onChange={(event) => {
                setStartDate(event.target.value)
                setPeriod('custom')
              }}
            />
          </label>
          <label>
            Tugash sanasi
            <input
              type="date"
              value={endDate}
              min={startDate}
              onChange={(event) => {
                setEndDate(event.target.value)
                setPeriod('custom')
              }}
            />
          </label>
        </div>
      </section>

      {query.isLoading ? (
        <div className="dispatcher-loading" role="status"><span /> Hisobot yuklanmoqda…</div>
      ) : query.isError ? (
        <div className="dispatcher-error-state" role="alert">
          <p>{apiErrorMessage(query.error, 'Hisobotni yuklab bo‘lmadi.')}</p>
          <button type="button" onClick={() => void query.refetch()}>Qayta urinish</button>
        </div>
      ) : data ? (
        <>
          <section className="dispatcher-report-summary" aria-label={`${title} jami ko‘rsatkichlari`}>
            {Object.entries(summary).map(([key, value]) => (
              <article className="dispatcher-card dispatcher-report-metric" key={key}>
                <span>{summaryLabels[key] ?? key}</span>
                <strong>{key.endsWith('_amount') || key.endsWith('_total') ? money(value) : value}</strong>
              </article>
            ))}
          </section>

          {report === 'sales' && (
            <ReportTable
              title="Kunlik savdo"
              columns={['Sana', 'Yetkazilgan buyurtmalar', 'Yetkazilgan summa', 'Bekor qilingan', 'Muammoli buyurtmalar']}
              rows={(data.rows as SalesRow[]).map((row) => [
                dateLabel(row.date),
                row.delivered_orders,
                money(row.delivered_amount),
                row.cancelled_orders,
                row.problem_orders,
              ])}
            />
          )}
          {report === 'debtors' && (
            <div className="dispatcher-report-debt-sections">
              <DebtorTable title="Qarzdor do‘konlar" rows={data.debtors ?? []} />
              <DebtorTable title="Oldindan to‘langan do‘konlar" rows={data.prepaid ?? []} />
            </div>
          )}
          {report === 'drivers' && (
            <ReportTable
              title="Haydovchilar faoliyati"
              columns={['Haydovchi telefoni', 'Reyslar', 'Yetkazilgan do‘konlar', 'Muammoli do‘konlar', 'Do‘kon yopiq', 'Qabul qilmadi', 'Qisman yetkazildi', 'Boshqa']}
              rows={(data.rows as DriverRow[]).map((row) => [
                row.driver_phone,
                row.trips,
                row.delivered_shops,
                row.problem_shops,
                row.reasons.shop_closed?.count ?? 0,
                row.reasons.refused?.count ?? 0,
                row.reasons.partial_delivery?.count ?? 0,
                row.reasons.other?.count ?? 0,
              ])}
            />
          )}
          {report === 'products' && (
            <ReportTable
              title="Eng ko‘p yetkazilgan mahsulotlar"
              columns={['Mahsulot', 'Birlik', 'Yetkazilgan miqdor', 'Yetkazilgan summa']}
              rows={(data.rows as ProductRow[]).map((row) => [
                row.product_name,
                row.unit,
                row.delivered_quantity,
                money(row.delivered_amount),
              ])}
            />
          )}
          {report === 'debtors' && (
            <p className="dispatcher-report-note">Qarz joriy ShopBalance holatini ko‘rsatadi; tanlangan sana oralig‘i qarz miqdoriga ta’sir qilmaydi.</p>
          )}
        </>
      ) : null}
      {exportError && <p className="dispatcher-report-export-error" role="alert">{exportError}</p>}
    </section>
  )
}

const summaryLabels: Record<string, string> = {
  delivered_orders: 'Yetkazilgan buyurtmalar',
  delivered_amount: 'Yetkazilgan savdo',
  cancelled_orders: 'Bekor qilingan buyurtmalar',
  problem_orders: 'Muammoli buyurtmalar',
  debtor_shops: 'Qarzdor do‘konlar',
  debt_total: 'Jami qarz',
  prepaid_shops: 'Oldindan to‘lagan do‘konlar',
  prepaid_total: 'Oldindan to‘lov',
  trips: 'Reyslar',
  delivered_shops: 'Yetkazilgan do‘konlar',
  problem_shops: 'Muammoli do‘konlar',
  products: 'Mahsulotlar',
}

function ReportTable({ title, columns, rows }: { title: string; columns: string[]; rows: Array<Array<string | number>> }) {
  return (
    <section className="dispatcher-card dispatcher-report-table-card">
      <div className="dispatcher-report-table-heading"><FileText size={17} /><h2>{title}</h2></div>
      <div className="dispatcher-report-table-scroll">
        <table className="dispatcher-orders-table">
          <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>
            ))}
            {!rows.length && <tr><td colSpan={columns.length} className="dispatcher-report-empty">Tanlangan oraliqda ma’lumot yo‘q.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function DebtorTable({ title, rows }: { title: string; rows: DebtorRow[] }) {
  return (
    <ReportTable
      title={title}
      columns={['Do‘kon', 'Joriy qarz', 'Oxirgi to‘lov sanasi']}
      rows={rows.map((row) => [
        row.shop_name,
        money(row.current_balance),
        dateLabel(row.last_payment_date),
      ])}
    />
  )
}
