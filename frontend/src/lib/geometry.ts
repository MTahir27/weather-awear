import type { RiskLevel } from '../api/schemas'

export type LonLat = [number, number]

const EARTH_RADIUS_MI = 3958.7613

export function haversineMiles([lon1, lat1]: LonLat, [lon2, lat2]: LonLat): number {
  const toRad = Math.PI / 180
  const dLat = (lat2 - lat1) * toRad
  const dLon = (lon2 - lon1) * toRad
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.min(1, Math.sqrt(h)))
}

export interface RiskStretch {
  level: RiskLevel | null
  path: LonLat[]
}

/**
 * Splits a route path into stretches coloured by checkpoint risk.
 *
 * Mirrors the backend's scoring: each checkpoint owns the road between the
 * midpoints to its neighbours. Adjacent stretches with the same level are
 * merged so the map draws as few segments as possible. The path is measured
 * locally and scaled to the route's reported length so the two agree.
 */
export function riskStretches(
  path: LonLat[],
  checkpoints: { mile: number; level: RiskLevel | null }[],
  totalMiles: number,
): RiskStretch[] {
  if (path.length < 2 || checkpoints.length === 0) return []

  const cumulative = [0]
  for (let i = 1; i < path.length; i++) {
    cumulative.push(cumulative[i - 1]! + haversineMiles(path[i - 1]!, path[i]!))
  }
  const measured = cumulative[cumulative.length - 1]!
  const scale = measured > 0 ? totalMiles / measured : 1
  const along = cumulative.map((d) => d * scale)

  // Merge consecutive checkpoints with the same level into [start, end) ranges.
  const ranges: { level: RiskLevel | null; start: number; end: number }[] = []
  checkpoints.forEach((checkpoint, i) => {
    const next = checkpoints[i + 1]
    const start = i === 0 ? 0 : (checkpoints[i - 1]!.mile + checkpoint.mile) / 2
    const end = next ? (checkpoint.mile + next.mile) / 2 : totalMiles
    const last = ranges[ranges.length - 1]
    if (last && last.level === checkpoint.level) last.end = end
    else ranges.push({ level: checkpoint.level, start, end })
  })

  const pointAt = (miles: number, index: number): LonLat => {
    const [a, b] = [path[index]!, path[index + 1] ?? path[index]!]
    const span = (along[index + 1] ?? along[index]!) - along[index]!
    const t = span > 0 ? (miles - along[index]!) / span : 0
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
  }

  const stretches: RiskStretch[] = []
  let index = 0
  for (const range of ranges) {
    while (index < path.length - 2 && along[index + 1]! <= range.start) index++
    const segment: LonLat[] = [pointAt(range.start, index)]
    while (index < path.length - 1 && along[index + 1]! < range.end) {
      index++
      segment.push(path[index]!)
    }
    segment.push(pointAt(Math.min(range.end, totalMiles), index))
    stretches.push({ level: range.level, path: segment })
  }
  return stretches
}

/** [[west, south], [east, north]] covering every path. */
export function boundsOf(paths: LonLat[][]): [LonLat, LonLat] | null {
  let west = Infinity
  let south = Infinity
  let east = -Infinity
  let north = -Infinity
  for (const path of paths) {
    for (const [lon, lat] of path) {
      west = Math.min(west, lon)
      east = Math.max(east, lon)
      south = Math.min(south, lat)
      north = Math.max(north, lat)
    }
  }
  return Number.isFinite(west)
    ? [
        [west, south],
        [east, north],
      ]
    : null
}

/** Point `miles` along the path, with the path scaled to `totalMiles` (clamped). */
export function pointAtMile(path: LonLat[], totalMiles: number, miles: number): LonLat {
  if (path.length === 0) throw new Error('Path is empty')
  const cumulative = [0]
  for (let i = 1; i < path.length; i++) {
    cumulative.push(cumulative[i - 1]! + haversineMiles(path[i - 1]!, path[i]!))
  }
  const measured = cumulative[cumulative.length - 1]!
  const target = measured > 0 && totalMiles > 0 ? (miles / totalMiles) * measured : 0
  if (target <= 0) return path[0]!
  if (target >= measured) return path[path.length - 1]!
  let i = 1
  while (cumulative[i]! < target) i++
  const [a, b] = [path[i - 1]!, path[i]!]
  const span = cumulative[i]! - cumulative[i - 1]!
  const t = span > 0 ? (target - cumulative[i - 1]!) / span : 0
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
}
