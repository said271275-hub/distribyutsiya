import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { AlertTriangle, ArrowDownToLine, ArrowUpFromLine, History, Package } from 'lucide-react'
import api, { apiErrorMessage } from './api'
import './InventoryPage.css'

type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

type StockRow = {
  product_id: number
  product_name: string
  unit: string
  current_quantity: string
  reserved_quantity: string
  available_quantity: string
  minimum_quantity: string
  is_low_stock: boolean
}

type InventoryEntry = {
  id: number
  product_id: number
  product_name: string
  unit: string
  entry_type: string
  quantity_delta: string
  reserved_delta: string
  batch_number: string
  reason: string
  occurred_at: string
  order_id: number | null
  trip_id: number | null
  reversal_of_id: number | null
  reversal_id: number | null
  can_reverse: boolean
}

type MovementRequest = {
  method: 'post' | 'patch'
  path: string
  payload: Record<string, string | number>
}

const movementNames: Record<string, string> = {
  receipt: 'Kirim',
  issue: 'Chiqim',
  adjustment: 'Tuzatish',
  reservation: 'Zaxira',
  release: 'Zaxira qaytarildi',
  delivery: 'Yetkazildi',
  reversal: 'Teskari yozuv',
}

const unitNames: Record<string, string> = {
  piece: 'dona',
  box: 'quti',
  block: 'blok',
}

function localDate() {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
}

function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === 'object') {
      for (const value of Object.values(data)) {
        if (typeof value === 'string') return value
        if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
      }
    }
  }
  return apiErrorMessage(error, 'Amalni bajarib bo‘lmadi.')
}

function inputValue(form: HTMLFormElement, name: string) {
  return String(new FormData(form).get(name) ?? '').trim()
}

function movementTime(value: string) {
  return new Date(value).toLocaleString('uz-UZ', {
    timeZone: 'Asia/Tashkent',
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

export default function InventoryPage() {
  const queryClient = useQueryClient()
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null)
  const [stockPage, setStockPage] = useState(1)
  const [entryPage, setEntryPage] = useState(1)
  const [receiptDate, setReceiptDate] = useState(localDate)
  const [reversingEntryId, setReversingEntryId] = useState<number | null>(null)
  const [error, setError] = useState('')

  const stocksQuery = useQuery({
    queryKey: ['inventory-stocks', stockPage],
    queryFn: async () => {
      const { data } = await api.get<Page<StockRow>>('/v1/admin/inventory/', {
        params: { page: stockPage, page_size: 100 },
      })
      return data
    },
  })

  const entriesQuery = useQuery({
    queryKey: ['inventory-entries', selectedProductId, entryPage],
    enabled: selectedProductId !== null,
    queryFn: async () => {
      const { data } = await api.get<Page<InventoryEntry>>('/v1/admin/inventory-entries/', {
        params: { product_id: selectedProductId, page: entryPage, page_size: 100 },
      })
      return data
    },
  })

  const movementMutation = useMutation({
    mutationFn: async ({ method, path, payload }: MovementRequest) => {
      const { data } = await api.request({ method, url: path, data: payload })
      return data
    },
    onSuccess: async () => {
      setError('')
      setReversingEntryId(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['inventory-stocks'] }),
        queryClient.invalidateQueries({ queryKey: ['inventory-entries'] }),
      ])
    },
    onError: (reason) => setError(errorMessage(reason)),
  })

  const submitMovement = async (
    event: FormEvent<HTMLFormElement>,
    path: string,
    payload: Record<string, string | number>,
    method: MovementRequest['method'] = 'post',
  ) => {
    event.preventDefault()
    const form = event.currentTarget
    setError('')
    try {
      await movementMutation.mutateAsync({ method, path, payload })
      form.reset()
    } catch (reason) {
      setError(errorMessage(reason))
    }
  }

  const stocks = stocksQuery.data?.results ?? []
  const entries = entriesQuery.data?.results ?? []

  return (
    <section className="inventory-page">
      <div className="dispatcher-page-heading">
        <div>
          <span className="dispatcher-eyebrow">MAHSULOT HISOBI</span>
          <h1>Ombor</h1>
          <p>Kirim, chiqim va tuzatishlarni o‘chirilmaydigan jurnal orqali yuriting.</p>
        </div>
      </div>

      {error && <p className="inventory-error" role="alert">{error}</p>}
      {stocksQuery.isError && (
        <p className="inventory-error" role="alert">{errorMessage(stocksQuery.error)}</p>
      )}

      <div className="inventory-forms">
        <form
          className="dispatcher-card inventory-form"
          onSubmit={(event) => {
            const form = event.currentTarget
            void submitMovement(event, '/v1/admin/inventory/receipt/', {
              product_id: inputValue(form, 'product_id'),
              quantity: inputValue(form, 'quantity'),
              batch_number: inputValue(form, 'batch_number'),
              date: receiptDate,
              note: inputValue(form, 'note'),
            })
          }}
        >
          <h2><ArrowDownToLine size={17} /> Kirim kiritish</h2>
          <label>Mahsulot
            <select name="product_id" required defaultValue="">
              <option value="" disabled>Mahsulotni tanlang</option>
              {stocks.map((stock) => (
                <option key={stock.product_id} value={stock.product_id}>{stock.product_name}</option>
              ))}
            </select>
          </label>
          <div className="inventory-form-row">
            <label>Miqdor
              <input name="quantity" type="number" min="0.01" step="0.01" required />
            </label>
            <label>Sana
              <input
                type="date"
                required
                value={receiptDate}
                onChange={(event) => setReceiptDate(event.target.value)}
              />
            </label>
          </div>
          <label>Partiya
            <input name="batch_number" maxLength={120} />
          </label>
          <label>Izoh
            <input name="note" maxLength={400} />
          </label>
          <button type="submit" disabled={movementMutation.isPending || stocks.length === 0}>
            Kirimni saqlash
          </button>
        </form>

        <form
          className="dispatcher-card inventory-form"
          onSubmit={(event) => {
            const form = event.currentTarget
            void submitMovement(event, '/v1/admin/inventory/issue/', {
              product_id: inputValue(form, 'product_id'),
              quantity: inputValue(form, 'quantity'),
              reason: inputValue(form, 'reason'),
            })
          }}
        >
          <h2><ArrowUpFromLine size={17} /> Chiqim kiritish</h2>
          <label>Mahsulot
            <select name="product_id" required defaultValue="">
              <option value="" disabled>Mahsulotni tanlang</option>
              {stocks.map((stock) => (
                <option key={stock.product_id} value={stock.product_id}>{stock.product_name}</option>
              ))}
            </select>
          </label>
          <label>Miqdor
            <input name="quantity" type="number" min="0.01" step="0.01" required />
          </label>
          <label>Sabab
            <input name="reason" maxLength={400} required />
          </label>
          <button type="submit" disabled={movementMutation.isPending || stocks.length === 0}>
            Chiqimni saqlash
          </button>
        </form>

        <form
          className="dispatcher-card inventory-form"
          onSubmit={(event) => {
            const form = event.currentTarget
            void submitMovement(event, '/v1/admin/inventory/adjustment/', {
              product_id: inputValue(form, 'product_id'),
              quantity_delta: inputValue(form, 'quantity_delta'),
              reason: inputValue(form, 'reason'),
              note: inputValue(form, 'note'),
            })
          }}
        >
          <h2><Package size={17} /> Tuzatish kiritish</h2>
          <label>Mahsulot
            <select name="product_id" required defaultValue="">
              <option value="" disabled>Mahsulotni tanlang</option>
              {stocks.map((stock) => (
                <option key={stock.product_id} value={stock.product_id}>{stock.product_name}</option>
              ))}
            </select>
          </label>
          <label>Miqdor (qo‘shish yoki ayirish)
            <input name="quantity_delta" type="number" step="0.01" required />
          </label>
          <label>Sabab
            <select name="reason" required defaultValue="inventory">
              <option value="inventory">Inventarizatsiya</option>
              <option value="damaged">Brak</option>
              <option value="lost">Yo‘qotish</option>
            </select>
          </label>
          <label>Izoh
            <input name="note" maxLength={400} />
          </label>
          <button type="submit" disabled={movementMutation.isPending || stocks.length === 0}>
            Tuzatishni saqlash
          </button>
        </form>
      </div>

      <section className="dispatcher-card inventory-stock-card">
        <div className="inventory-card-heading">
          <h2><Package size={17} /> Mahsulot qoldiqlari</h2>
          {stocksQuery.isFetching && <span>Yangilanmoqda…</span>}
        </div>
        <div className="inventory-table-scroll">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Mahsulot</th>
                <th>Omborda</th>
                <th>Zaxirada</th>
                <th>Bo‘sh qoldiq</th>
                <th>Eng kam qoldiq</th>
                <th>Harakatlar</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((stock) => (
                <tr key={stock.product_id}>
                  <td>
                    <strong>{stock.product_name}</strong>
                    {stock.is_low_stock && (
                      <span className="inventory-low-stock"><AlertTriangle size={13} /> Qoldiq kam</span>
                    )}
                  </td>
                  <td>{stock.current_quantity} {unitNames[stock.unit] ?? stock.unit}</td>
                  <td>{stock.reserved_quantity}</td>
                  <td>{stock.available_quantity}</td>
                  <td>
                    <form
                      className="inventory-minimum-form"
                      onSubmit={(event) => {
                        const form = event.currentTarget
                        void submitMovement(
                          event,
                          `/v1/admin/inventory/${stock.product_id}/minimum/`,
                          { minimum_quantity: inputValue(form, 'minimum_quantity') },
                          'patch',
                        )
                      }}
                    >
                      <input
                        name="minimum_quantity"
                        aria-label={`${stock.product_name} eng kam qoldig‘i`}
                        type="number"
                        min="0"
                        step="0.01"
                        defaultValue={stock.minimum_quantity}
                      />
                      <button type="submit" disabled={movementMutation.isPending}>Saqlash</button>
                    </form>
                  </td>
                  <td>
                    <button
                      className="inventory-history-button"
                      type="button"
                      onClick={() => {
                        setSelectedProductId(stock.product_id)
                        setEntryPage(1)
                      }}
                    >
                      <History size={15} /> Tarix
                    </button>
                  </td>
                </tr>
              ))}
              {stocks.length === 0 && !stocksQuery.isLoading && (
                <tr><td colSpan={6} className="inventory-empty">Mahsulot topilmadi.</td></tr>
              )}
              {stocksQuery.isLoading && (
                <tr><td colSpan={6} className="inventory-empty">Yuklanmoqda…</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {stocksQuery.data && stocksQuery.data.count > 100 && (
          <div className="inventory-pagination">
            <span>{stocksQuery.data.count} ta mahsulot</span>
            <button type="button" disabled={!stocksQuery.data.previous} onClick={() => setStockPage((page) => page - 1)}>Oldingi</button>
            <button type="button" disabled={!stocksQuery.data.next} onClick={() => setStockPage((page) => page + 1)}>Keyingi</button>
          </div>
        )}
      </section>

      {selectedProductId !== null && (
        <section className="dispatcher-card inventory-history-card">
          <div className="inventory-card-heading">
            <h2><History size={17} /> {stocks.find((stock) => stock.product_id === selectedProductId)?.product_name ?? 'Mahsulot'} harakatlari</h2>
            <button type="button" className="inventory-history-button" onClick={() => setSelectedProductId(null)}>
              Yopish
            </button>
          </div>
          {entriesQuery.isError && (
            <p className="inventory-error" role="alert">{errorMessage(entriesQuery.error)}</p>
          )}
          <div className="inventory-table-scroll">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Sana</th>
                  <th>Harakat</th>
                  <th>Miqdor</th>
                  <th>Partiya / izoh</th>
                  <th>Teskari yozuv</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{movementTime(entry.occurred_at)}</td>
                    <td>{movementNames[entry.entry_type] ?? entry.entry_type}</td>
                    <td>{entry.quantity_delta} {unitNames[entry.unit] ?? entry.unit}</td>
                    <td>{entry.batch_number ? `${entry.batch_number} · ` : ''}{entry.reason || '—'}</td>
                    <td>
                      {entry.can_reverse && reversingEntryId !== entry.id && (
                        <button
                          className="inventory-history-button"
                          type="button"
                          onClick={() => setReversingEntryId(entry.id)}
                        >
                          Tuzatish
                        </button>
                      )}
                      {entry.reversal_id && <span>Teskari yozuv #{entry.reversal_id}</span>}
                      {entry.reversal_of_id && <span>#{entry.reversal_of_id} yozuviga teskari</span>}
                      {reversingEntryId === entry.id && (
                        <form
                          className="inventory-reverse-form"
                          onSubmit={(event) => {
                            const form = event.currentTarget
                            void submitMovement(event, `/v1/admin/inventory-entries/${entry.id}/reverse/`, {
                              reason: inputValue(form, 'reason'),
                            })
                          }}
                        >
                          <input name="reason" aria-label="Teskari yozuv sababi" required maxLength={400} />
                          <button type="submit" disabled={movementMutation.isPending}>Yozish</button>
                          <button type="button" onClick={() => setReversingEntryId(null)}>Bekor</button>
                        </form>
                      )}
                    </td>
                  </tr>
                ))}
                {entries.length === 0 && !entriesQuery.isLoading && (
                  <tr><td colSpan={5} className="inventory-empty">Harakatlar hali yo‘q.</td></tr>
                )}
                {entriesQuery.isLoading && (
                  <tr><td colSpan={5} className="inventory-empty">Yuklanmoqda…</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {entriesQuery.data && entriesQuery.data.count > 100 && (
            <div className="inventory-pagination">
              <span>{entriesQuery.data.count} ta yozuv</span>
              <button type="button" disabled={!entriesQuery.data.previous} onClick={() => setEntryPage((page) => page - 1)}>Oldingi</button>
              <button type="button" disabled={!entriesQuery.data.next} onClick={() => setEntryPage((page) => page + 1)}>Keyingi</button>
            </div>
          )}
        </section>
      )}
    </section>
  )
}
