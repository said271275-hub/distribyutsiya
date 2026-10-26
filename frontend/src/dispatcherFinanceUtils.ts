export type FinanceEntry = {
  id: number
  amount: string
  direction: 'debit' | 'credit'
  order_id: number | null
  payment_id: number | null
  note: string
  posted_at: string | null
  created_at: string
}

export type FinanceBalance = {
  id: number
  shop_id: number
  shop_name: string
  current_balance: string
  container_deposit: string
  last_payment_at: string | null
  entries: FinanceEntry[]
}

export function filterFinanceBalances(
  balances: FinanceBalance[],
  search: string,
  debtorsOnly: boolean,
) {
  const query = search.trim().toLocaleLowerCase('uz-UZ')
  return balances.filter((balance) => {
    const matchesSearch = !query || balance.shop_name.toLocaleLowerCase('uz-UZ').includes(query)
    const matchesDebt = !debtorsOnly || Number(balance.current_balance) > 0
    return matchesSearch && matchesDebt
  })
}

export function financeEntryLabel(entry: FinanceEntry) {
  return entry.direction === 'debit' ? 'Qarz qo‘shildi' : 'Qarz kamaydi'
}

export function formatFinanceMoney(value: string | number) {
  return `${new Intl.NumberFormat('uz-UZ', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} so‘m`
}

export function formatFinanceBalance(value: string | number) {
  const balance = Number(value)
  if (balance > 0) return `Do‘kon qarzdor: ${formatFinanceMoney(balance)}`
  if (balance < 0) return `Oldindan to‘langan: ${formatFinanceMoney(Math.abs(balance))}`
  return 'Qarz yo‘q'
}

export function formatFinanceDate(value: string | null) {
  if (!value) return 'Kiritilmagan'
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)
  if (Number.isNaN(date.getTime())) return 'Sana noto‘g‘ri'
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}.${month}.${date.getFullYear()}`
}
