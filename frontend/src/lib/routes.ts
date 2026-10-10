import { RISK_LEVELS, type Route } from '../api/schemas'
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
