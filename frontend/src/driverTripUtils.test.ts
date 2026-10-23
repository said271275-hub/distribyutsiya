import { describe, expect, it } from 'vitest'
import { getDriverTripProgress, sortDriverStops } from './driverTripUtils'

describe('driver trip progress', () => {
  it('moves undelivered shops ahead while preserving route order', () => {
    const stops = [
      { id: 3, sequence: 3, delivered_at: null },
      { id: 1, sequence: 1, delivered_at: '2026-01-01T10:00:00Z' },
      { id: 2, sequence: 2, delivered_at: null },
    ]

    expect(sortDriverStops(stops).map((stop) => stop.id)).toEqual([2, 3, 1])
    expect(stops.map((stop) => stop.id)).toEqual([3, 1, 2])
  })

  it('counts delivered shops and reports a percentage', () => {
    expect(getDriverTripProgress([
      { id: 1, delivered_at: '2026-01-01T10:00:00Z' },
      { id: 2, delivered_at: null },
      { id: 3, delivered_at: '2026-01-01T11:00:00Z' },
    ])).toEqual({ completed: 2, total: 3, percentage: 67 })
    expect(getDriverTripProgress([])).toEqual({ completed: 0, total: 0, percentage: 0 })
  })
})
