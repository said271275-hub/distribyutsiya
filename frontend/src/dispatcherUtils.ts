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
  const [year, month, day] = value.split('-').map(Number)
  const monthNames = [
    'yanvar',
    'fevral',
    'mart',
    'aprel',
    'may',
    'iyun',
    'iyul',
    'avgust',
    'sentabr',
    'oktabr',
    'noyabr',
    'dekabr',
  ]
  if (!year || !month || !day || month > 12 || day > 31) return value
  return `${day}-${monthNames[month - 1]} ${year}-yil`
}

export function getSuggestionLoad(
  stops: Array<{ capacity_load: string | null; capacity_metric: string }>,
) {
  const metric = stops[0]?.capacity_metric ?? 'unknown'
  if (
    metric === 'unknown' ||
    stops.some((stop) => stop.capacity_metric !== metric || stop.capacity_load === null)
  ) {
    return { metric: 'unknown', load: null }
  }
  return {
    metric,
    load: stops.reduce((total, stop) => total + Number(stop.capacity_load), 0),
  }
}
