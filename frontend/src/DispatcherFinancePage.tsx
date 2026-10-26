import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Check, CreditCard, Search, Wallet } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import api, { apiErrorMessage } from './api'
import {
  filterFinanceBalances,
  financeEntryLabel,
  formatFinanceBalance,
  formatFinanceDate,
  formatFinanceMoney,
  type FinanceBalance,
} from './dispatcherFinanceUtils'
import './DispatcherFinance.css'

type Page<T> = { results: T[]; count: number; next: string | null; previous: string | null }
type PaymentValues = {
  amount: string
  paid_at: string
  method: 'cash' | 'card' | 'bank_transfer' | 'other'
  note: string
}
type AdjustmentValues = { amount: string; direction: 'debit' | 'credit'; note: string }

const paymentSchema = z.object({
  amount: z.string().trim().refine((value) => Number.isFinite(Number(value)) && Number(value) > 0, 'Summani noldan katta kiriting.'),
  paid_at: z.string().min(1, 'To‘lov sanasini tanlang.'),
  method: z.enum(['cash', 'card', 'bank_transfer', 'other']),
  note: z.string().trim().max(500, 'Izoh 500 belgidan oshmasin.'),
})

const adjustmentSchema = z.object({
  amount: z.string().trim().refine((value) => Number.isFinite(Number(value)) && Number(value) > 0, 'Summani noldan katta kiriting.'),
  direction: z.enum(['debit', 'credit']),
  note: z.string().trim().min(1, 'Tuzatish sababini yozing.').max(500, 'Izoh 500 belgidan oshmasin.'),
})

const emptyBalances: FinanceBalance[] = []
const emptyPayment: PaymentValues = {
  amount: '',
  paid_at: new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10),
  method: 'cash',
  note: '',
}
const emptyAdjustment: AdjustmentValues = { amount: '', direction: 'credit', note: '' }

export default function DispatcherFinancePage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [debtorsOnly, setDebtorsOnly] = useState(false)
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null)
  const paymentForm = useForm<PaymentValues>({
    resolver: zodResolver(paymentSchema),
    defaultValues: emptyPayment,
  })
  const adjustmentForm = useForm<AdjustmentValues>({
    resolver: zodResolver(adjustmentSchema),
    defaultValues: emptyAdjustment,
  })
  const balancesQuery = useQuery({
    queryKey: ['dispatcher-finances'],
    queryFn: async () => {
      const balances: FinanceBalance[] = []
      let response = await api.get<Page<FinanceBalance>>(
        '/v1/admin/balances/',
        { params: { page_size: 100 } },
      )
      while (true) {
        balances.push(...response.data.results)
        if (!response.data.next) return balances
        response = await api.get<Page<FinanceBalance>>(response.data.next)
      }
    },
  })
  const balances = balancesQuery.data ?? emptyBalances
  const visibleBalances = useMemo(
    () => filterFinanceBalances(balances, search, debtorsOnly),
    [balances, debtorsOnly, search],
  )
  const selectedBalance = visibleBalances.find((balance) => balance.shop_id === selectedShopId)
    ?? visibleBalances[0]
    ?? null

  const refreshBalances = async () => {
    await queryClient.invalidateQueries({ queryKey: ['dispatcher-finances'] })
  }
  const createPayment = useMutation({
    mutationFn: async (values: PaymentValues) => api.post('/v1/admin/payments/', {
      shop_id: selectedBalance?.shop_id,
      amount: values.amount,
      paid_at: values.paid_at,
      method: values.method,
      note: values.note,
    }),
    onSuccess: async () => {
      paymentForm.reset(emptyPayment)
      await refreshBalances()
    },
  })
  const createAdjustment = useMutation({
    mutationFn: async (values: AdjustmentValues) => api.post('/v1/admin/balances/adjust/', {
      shop_id: selectedBalance?.shop_id,
      amount: values.amount,
      direction: values.direction,
      note: values.note,
    }),
    onSuccess: async () => {
      adjustmentForm.reset(emptyAdjustment)
      await refreshBalances()
    },
  })

  return (
    <section className="dispatcher-finance-page">
      <div className="dispatcher-page-heading">
        <div>
          <span className="dispatcher-eyebrow">HISOB-KITOB</span>
          <h1>Qarz va to‘lov</h1>
          <p>Do‘konlar qarzi, to‘lovlar va o‘zgarmas hisob-kitob yozuvlarini ko‘ring.</p>
        </div>
      </div>

      {balancesQuery.isLoading ? (
        <div className="dispatcher-loading" role="status"><span /> Hisob-kitoblar yuklanmoqda…</div>
      ) : balancesQuery.isError ? (
        <div className="dispatcher-error-state" role="alert">
          <p>{apiErrorMessage(balancesQuery.error, 'Hisob-kitoblarni yuklab bo‘lmadi.')}</p>
          <button type="button" onClick={() => void balancesQuery.refetch()}>Qayta urinish</button>
        </div>
      ) : (
        <>
          <section className="dispatcher-card dispatcher-finance-card">
            <div className="dispatcher-finance-toolbar">
              <label className="dispatcher-finance-search">
                <Search size={16} />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Do‘kon nomi bo‘yicha qidirish"
                  aria-label="Do‘konlarni qidirish"
                />
              </label>
              <label className="dispatcher-finance-debt-filter">
                <input
                  type="checkbox"
                  checked={debtorsOnly}
                  onChange={(event) => setDebtorsOnly(event.target.checked)}
                />
                Qarzdorlar
              </label>
            </div>
            <div className="dispatcher-finance-layout">
              <div className="dispatcher-finance-shop-list" aria-label="Do‘konlar qarzi">
                {visibleBalances.map((balance) => (
                  <button
                    type="button"
                    key={balance.shop_id}
                    className={`dispatcher-finance-shop${selectedBalance?.shop_id === balance.shop_id ? ' dispatcher-finance-shop-selected' : ''}`}
                    onClick={() => setSelectedShopId(balance.shop_id)}
                  >
                    <span className="dispatcher-finance-shop-copy">
                      <strong>{balance.shop_name}</strong>
                      <small>Oxirgi to‘lov: {formatFinanceDate(balance.last_payment_at)}</small>
                    </span>
                    <b>{formatFinanceBalance(balance.current_balance)}</b>
                  </button>
                ))}
                {!visibleBalances.length && (
                  <div className="dispatcher-empty">
                    <Wallet size={22} /><strong>Do‘kon topilmadi</strong>
                    <span>Qidiruv yoki qarzdorlar filtrini o‘zgartiring.</span>
                  </div>
                )}
              </div>

              {selectedBalance ? (
                <div className="dispatcher-finance-details">
                  <div className="dispatcher-finance-detail-heading">
                    <div><span className="dispatcher-eyebrow">DO‘KON HISOBI</span><h2>{selectedBalance.shop_name}</h2></div>
                    <div className="dispatcher-finance-balances">
                      <span><small>Saldo holati</small><strong>{formatFinanceBalance(selectedBalance.current_balance)}</strong></span>
                      <span><small>Tara depoziti</small><strong>{formatFinanceMoney(selectedBalance.container_deposit)}</strong></span>
                    </div>
                  </div>

                  <section className="dispatcher-finance-ledger">
                    <div className="dispatcher-finance-section-heading">
                      <div><span className="dispatcher-eyebrow">O‘CHIRILMAYDIGAN YOZUVLAR</span><h3>Hisob-kitob tarixi</h3></div>
                    </div>
                    {selectedBalance.entries.length ? (
                      <div className="dispatcher-table-scroll">
                        <table className="dispatcher-orders-table">
                          <thead><tr><th>Sana</th><th>Qarz o‘zgarishi</th><th>Izoh</th><th>Qarzga ta’siri</th></tr></thead>
                          <tbody>
                            {selectedBalance.entries.map((entry) => (
                              <tr key={entry.id}>
                                <td>{formatFinanceDate(entry.posted_at ?? entry.created_at)}</td>
                                <td>{financeEntryLabel(entry)}</td>
                                <td className="dispatcher-finance-note">{entry.note || '—'}</td>
                                <td className={`dispatcher-finance-entry-${entry.direction}`}>
                                  {entry.direction === 'debit' ? '+' : '−'}{formatFinanceMoney(entry.amount)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : <div className="dispatcher-empty">Hozircha hisob-kitob yozuvi yo‘q.</div>}
                  </section>

                  <div className="dispatcher-finance-forms">
                    <form
                      className="dispatcher-finance-form"
                      onSubmit={(event) => void paymentForm.handleSubmit((values) => createPayment.mutate(values))(event)}
                    >
                      <h3><CreditCard size={17} /> To‘lov kiritish</h3>
                      <label>Summa (so‘m)
                        <input {...paymentForm.register('amount')} inputMode="decimal" placeholder="Masalan, 250000" />
                        {paymentForm.formState.errors.amount && <small role="alert">{paymentForm.formState.errors.amount.message}</small>}
                      </label>
                      <label>Sana
                        <input type="date" {...paymentForm.register('paid_at')} />
                        {paymentForm.formState.errors.paid_at && <small role="alert">{paymentForm.formState.errors.paid_at.message}</small>}
                      </label>
                      <label>To‘lov turi
                        <select {...paymentForm.register('method')}>
                          <option value="cash">Naqd</option>
                          <option value="card">Karta</option>
                          <option value="bank_transfer">Bank o‘tkazmasi</option>
                          <option value="other">Boshqa</option>
                        </select>
                      </label>
                      <label>Izoh
                        <textarea {...paymentForm.register('note')} rows={2} maxLength={500} placeholder="Ixtiyoriy izoh" />
                        {paymentForm.formState.errors.note && <small role="alert">{paymentForm.formState.errors.note.message}</small>}
                      </label>
                      {createPayment.isError && <p className="dispatcher-finance-form-error" role="alert">{apiErrorMessage(createPayment.error, 'To‘lovni saqlab bo‘lmadi.')}</p>}
                      {createPayment.isSuccess && <p className="dispatcher-finance-form-success" role="status"><Check size={15} /> To‘lov qayd etildi.</p>}
                      <button type="submit" className="dispatcher-primary-button" disabled={createPayment.isPending}>
                        {createPayment.isPending ? 'Saqlanmoqda…' : 'To‘lovni qayd etish'}
                      </button>
                    </form>

                    <form
                      className="dispatcher-finance-form dispatcher-finance-adjustment"
                      onSubmit={(event) => void adjustmentForm.handleSubmit((values) => createAdjustment.mutate(values))(event)}
                    >
                      <h3><AlertCircle size={17} /> Xatoni tuzatish</h3>
                      <p>Eski yozuv o‘chirilmaydi; unga qarama-qarshi tuzatish yozuvi qo‘shiladi.</p>
                      <label>Tuzatish yo‘nalishi
                        <select {...adjustmentForm.register('direction')}>
                          <option value="credit">Qarzni kamaytirish</option>
                          <option value="debit">Qarzni oshirish</option>
                        </select>
                      </label>
                      <label>Summa (so‘m)
                        <input {...adjustmentForm.register('amount')} inputMode="decimal" placeholder="Tuzatiladigan summa" />
                        {adjustmentForm.formState.errors.amount && <small role="alert">{adjustmentForm.formState.errors.amount.message}</small>}
                      </label>
                      <label>Sabab
                        <textarea {...adjustmentForm.register('note')} rows={2} maxLength={500} placeholder="Tuzatish sababini yozing" />
                        {adjustmentForm.formState.errors.note && <small role="alert">{adjustmentForm.formState.errors.note.message}</small>}
                      </label>
                      {createAdjustment.isError && <p className="dispatcher-finance-form-error" role="alert">{apiErrorMessage(createAdjustment.error, 'Tuzatish yozuvini saqlab bo‘lmadi.')}</p>}
                      {createAdjustment.isSuccess && <p className="dispatcher-finance-form-success" role="status"><Check size={15} /> Tuzatish qayd etildi.</p>}
                      <button type="submit" className="dispatcher-order-action" disabled={createAdjustment.isPending}>
                        {createAdjustment.isPending ? 'Saqlanmoqda…' : 'Tuzatish yozuvini qo‘shish'}
                      </button>
                    </form>
                  </div>
                </div>
              ) : (
                <div className="dispatcher-empty dispatcher-finance-no-selection">
                  <Wallet size={24} /><strong>Do‘konni tanlang</strong>
                  <span>Qarz tarixi va to‘lov shakli shu yerda ko‘rinadi.</span>
                </div>
              )}
            </div>
            <div className="dispatcher-finance-footer">{visibleBalances.length} ta do‘kon ko‘rsatilmoqda. Ijobiy saldo — qarz; manfiy saldo — oldindan to‘lov.</div>
          </section>
        </>
      )}
    </section>
  )
}
