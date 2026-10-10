import { RISK_LEVELS, type RiskLevel, type Route } from '../api/schemas'
import { RISK_STYLE } from './risk'

/** Routes arrive ranked best-first; they are named A, B, C in that order. */
export function routeName(rank: number): string {
  return `Route ${String.fromCharCode(64 + rank)}`
}

export interface RiskSegment {
  key: string
  label: string
  hex: string
  miles: number
}

/** Miles at each risk level (plus unknown), omitting levels with no distance. */
export function riskSegments(risk: Route['risk']): RiskSegment[] {
  const segments: RiskSegment[] = RISK_LEVELS.map((level) => ({
    key: level,
    label: RISK_STYLE[level].label,
    hex: RISK_STYLE[level].hex,
    miles: risk.miles_by_level[level] ?? 0,
  }))
  segments.push({
    key: 'unknown',
    label: RISK_STYLE.unknown.label,
    hex: RISK_STYLE.unknown.hex,
    miles: risk.unknown_mi,
  })
  return segments.filter((s) => s.miles > 0)
}

const FLAGGED_LEVELS = [
  ['no_travel', 'No Travel'],
  ['severe', 'Severe'],
  ['high', 'High'],
] as const

/**
 * Short risk summary for a route label: miles at the levels that decide the
 * ranking (e.g. "High 25 mi"), Moderate miles when nothing worse exists, or
 * "All Low".
 */
export function riskSummary(risk: Route['risk']): string {
  const parts: string[] = FLAGGED_LEVELS.flatMap(([level, label]) => {
    const miles = Math.round(risk.miles_by_level[level] ?? 0)
    return miles > 0 ? [`${label} ${miles} mi`] : []
  })
  const unknown = Math.round(risk.unknown_mi)
  if (unknown > 0) parts.push(`Unknown ${unknown} mi`)
  if (parts.length) return parts.join(' · ')
  const moderate = Math.round(risk.miles_by_level.moderate ?? 0)
  return moderate > 0 ? `Moderate ${moderate} mi` : 'All Low'
}

/**
 * Where along each route its label sits (fraction of the distance), by rank.
 * Routes share their ends, so labels are staggered to keep them apart.
 */
export function labelFraction(rank: number): number {
  return [0.5, 0.3, 0.7][rank - 1] ?? 0.5
}

/**
 * Checkpoints that get an arrival-time label on the map: the origin, the first
 * checkpoint at or past every `everyMiles`, and the destination.
 */
export function etaLabelCheckpoints<T extends { mile: number }>(
  checkpoints: T[],
  everyMiles = 100,
): T[] {
  const chosen: T[] = []
  let nextMile = 0
  for (const checkpoint of checkpoints) {
    if (checkpoint.mile >= nextMile) {
      chosen.push(checkpoint)
      nextMile = (Math.floor(checkpoint.mile / everyMiles) + 1) * everyMiles
    }
  }
  const last = checkpoints.at(-1)
  if (last && chosen.at(-1) !== last) {
    // Avoid two labels crowding the destination.
    if (chosen.length > 1 && last.mile - chosen.at(-1)!.mile < everyMiles / 2) chosen.pop()
    chosen.push(last)
  }
  return chosen
}

export interface RiskBreakdownItem {
  key: RiskLevel | 'unknown'
  label: string
  miles: number
}

/**
 * Miles at each level that can decide the ranking (worst first), omitting
 * levels the route never reaches. Empty means the whole route is Low.
 */
export function riskBreakdown(risk: Route['risk']): RiskBreakdownItem[] {
  const items: RiskBreakdownItem[] = (['no_travel', 'severe', 'high', 'moderate'] as const).map(
    (level) => ({
      key: level,
      label: RISK_STYLE[level].label,
      miles: risk.miles_by_level[level] ?? 0,
    }),
  )
  items.push({ key: 'unknown', label: RISK_STYLE.unknown.label, miles: risk.unknown_mi })
  // Below 0.05 mi rounds to "0 mi" on screen, which would read as a contradiction.
  return items.filter((item) => item.miles >= 0.05)
}
