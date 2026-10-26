import { describe, expect, it } from 'vitest'
import { applyQueuedDriverAction, sortDriverActionsBySequence } from './driverOfflineUtils'
import type { QueuedDriverAction } from './driverOfflineStore'
import type { OfflineTrip } from './driverOfflineUtils'

const trip: OfflineTrip = {
  id: 10,
  status: 'in_progress',
  stops: [
    {
      id: 20,
      delivered_at: null,
      issue_history: [],
      orders: [{ id: 30, status: 'in_transit' }, { id: 31, status: 'in_transit' }],
    },
    {
      id: 21,
      delivered_at: null,
      issue_history: [],
      orders: [{ id: 32, status: 'in_transit' }],
    },
  ],
}

function action(overrides: Partial<QueuedDriverAction>): QueuedDriverAction {
  return {
    actionId: '8e1e9c73-65ea-44b0-872c-d9ce64a6e75a',
    actorId: 1,
    tripId: 10,
    stopId: 20,
    date: '2026-10-26',
    type: 'delivered',
    payload: {},
    createdAt: '2026-10-26T10:00:00.000Z',
    ...overrides,
  }
}

describe('offline driver actions', () => {
  it('orders queued actions by their IndexedDB sequence', () => {
    const earlier = action({ actionId: 'first', sequence: 1 })
    const later = action({ actionId: 'second', sequence: 2 })

    expect(sortDriverActionsBySequence([later, earlier]).map((item) => item.actionId))
      .toEqual(['first', 'second'])
  })

  it('marks a delivered stop and its orders in the local trip copy', () => {
    const updated = applyQueuedDriverAction([trip], action({}))

    expect(updated[0].stops[0].delivered_at).toBe('2026-10-26T10:00:00.000Z')
    expect(updated[0].stops[0].orders.every((order) => order.status === 'delivered')).toBe(true)
    expect(updated[0].status).toBe('in_progress')
    expect(trip.stops[0].delivered_at).toBeNull()
  })

  it('retains a partial-delivery issue and marks only orders with a delivered quantity', () => {
    const updated = applyQueuedDriverAction([trip], action({
      type: 'issue',
      payload: {
        reason: 'partial_delivery',
        note: 'Bir qismi yetkazildi',
        delivered_orders: [
          { order_id: 30, items: [{ item_id: 40, quantity: '1.00' }] },
          { order_id: 31, items: [{ item_id: 41, quantity: '0' }] },
        ],
      },
    }))

    expect(updated[0].stops[0].orders.map((order) => order.status)).toEqual(['delivered', 'in_transit'])
    expect(updated[0].stops[0].delivered_at).toBeNull()
    expect(updated[0].stops[0].issue_history[0].reason).toBe('partial_delivery')
    expect(updated[0].stops[0].issue_history[0].note).toBe('Bir qismi yetkazildi')
  })
})