export type OrderStatus =
  | 'new'
  | 'confirmed'
  | 'loaded'
  | 'in_transit'
  | 'delivered'
  | 'cancelled'

export type OrderFilters = {
  date: string
  status: OrderStatus | 'all'
  search: string
  page: number
}

export const orderStatusLabels: Record<OrderStatus, string> = {
  new: 'Yangi',
  confirmed: 'Tasdiqlandi',
  loaded: 'Yuklandi',
  in_transit: 'Yo‘lda',
  delivered: 'Yetkazildi',
  cancelled: 'Bekor qilindi',
}

export function buildOrderQueryParams(filters: OrderFilters) {
  const params: Record<string, string | number> = { page: filters.page }
  if (filters.date) params.date = filters.date
  if (filters.status !== 'all') params.status = filters.status
  if (filters.search.trim()) params.search = filters.search.trim()
  return params
}

export function formatCurrency(value: string | number) {
  return `${new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 0 }).format(Number(value))} so‘m`
}

export function formatOrderDate(value: string) {
  return new Intl.DateTimeFormat('uz-UZ', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(`${value}T00:00:00+05:00`))
}
