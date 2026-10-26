import type { QueuedDriverAction } from './driverOfflineStore'

export function sortDriverActionsBySequence(actions: QueuedDriverAction[]) {
  return [...actions].sort((left, right) => (left.sequence ?? 0) - (right.sequence ?? 0))
}

export type OfflineTrip = {
  id: number
  status: string
  stops: Array<{
    id: number
    delivered_at: string | null
    issue_history: Array<{ reason: string; note: string; created_at: string }>
    orders: Array<{ id: number; status: string }>
  }>
}

export function applyQueuedDriverAction<T extends OfflineTrip>(
  trips: T[],
  action: QueuedDriverAction,
): T[] {
  const actionTime = action.createdAt
  return trips.map((trip) => {
    if (trip.id !== action.tripId) return trip
    const stops = trip.stops.map((stop) => {
      if (stop.id !== action.stopId) return stop
      if (action.type === 'delivered') {
        return {
          ...stop,
          delivered_at: actionTime,
          orders: stop.orders.map((order) => ({ ...order, status: 'delivered' })),
        }
      }

      const deliveredOrderIds = new Set((action.payload.delivered_orders ?? [])
        .filter((order) => order.items.some((item) => Number(item.quantity) > 0))
        .map((order) => order.order_id))
      const orders = stop.orders.map((order) => {
        if (order.status === 'delivered') return order
        if (action.payload.reason === 'partial_delivery') {
          return { ...order, status: deliveredOrderIds.has(order.id) ? 'delivered' : 'in_transit' }
        }
        return { ...order, status: 'in_transit' }
      })
      const issue = {
        reason: action.payload.reason ?? 'other',
        note: action.payload.note ?? '',
        created_at: actionTime,
      }
      return {
        ...stop,
        delivered_at: orders.length && orders.every((order) => order.status === 'delivered')
          ? actionTime
          : stop.delivered_at,
        orders,
        issue_history: [...stop.issue_history, issue],
      }
    })
    return {
      ...trip,
      status: stops.length && stops.every((stop) => stop.delivered_at) ? 'completed' : 'in_progress',
      stops,
    }
  })
}