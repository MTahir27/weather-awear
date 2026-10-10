import type { Route } from '../api/schemas'

export type TruckStatus = 'waiting' | 'driving' | 'resting' | 'arrived'

export interface TruckProgress {
  mile: number
  status: TruckStatus
}

/**
 * Where the truck is (in miles along the route) at a moment in time.
 *
 * Uses checkpoint arrival times plus the start and end of each stop as
 * anchors, so the truck stays parked during a rest instead of creeping
 * between the checkpoints either side of it.
 */
export function truckProgressAt(route: Route, departureMs: number, atMs: number): TruckProgress {
  const anchors: [number, number][] = route.checkpoints.map((c) => [Date.parse(c.eta), c.mile])
  for (const stop of route.stops) {
    anchors.push([Date.parse(stop.starts_at), stop.mile], [Date.parse(stop.ends_at), stop.mile])
  }
  anchors.sort((a, b) => a[0] - b[0] || a[1] - b[1])

  const arrivalMs = Date.parse(route.arrival_time)
  if (atMs < departureMs) return { mile: 0, status: 'waiting' }
  if (atMs >= arrivalMs) return { mile: route.distance_mi, status: 'arrived' }

  const resting = route.stops.some(
    (s) => atMs >= Date.parse(s.starts_at) && atMs < Date.parse(s.ends_at),
  )
  let i = 1
  while (i < anchors.length - 1 && anchors[i]![0] <= atMs) i++
  const [t0, m0] = anchors[i - 1] ?? [departureMs, 0]
  const [t1, m1] = anchors[i] ?? [arrivalMs, route.distance_mi]
  const mile = t1 > t0 ? m0 + ((m1 - m0) * (atMs - t0)) / (t1 - t0) : m1
  return {
    mile: Math.min(Math.max(mile, 0), route.distance_mi),
    status: resting ? 'resting' : 'driving',
  }
}
