export type DriverStopProgressInput = {
  id: number
  sequence?: number
  delivered_at: string | null
}

export function sortDriverStops<T extends DriverStopProgressInput>(stops: readonly T[]): T[] {
  return [...stops].sort((first, second) => (
    Number(Boolean(first.delivered_at)) - Number(Boolean(second.delivered_at))
    || (first.sequence ?? first.id) - (second.sequence ?? second.id)
    || first.id - second.id
  ))
}

export function getDriverTripProgress(stops: readonly DriverStopProgressInput[]) {
  const completed = stops.filter((stop) => Boolean(stop.delivered_at)).length
  return {
    completed,
    total: stops.length,
    percentage: stops.length ? Math.round((completed / stops.length) * 100) : 0,
  }
}
