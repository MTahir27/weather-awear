import type { RiskLevel } from '../api/schemas'

/**
 * Risk palette. Lightness steps down as risk rises so levels stay
 * distinguishable without colour vision; every use is paired with a text label.
 */
export const RISK_STYLE: Record<RiskLevel | 'unknown', { label: string; hex: string }> = {
  low: { label: 'Low', hex: '#16a34a' },
  moderate: { label: 'Moderate', hex: '#eab308' },
  high: { label: 'High', hex: '#f97316' },
  severe: { label: 'Severe', hex: '#dc2626' },
  no_travel: { label: 'No Travel', hex: '#7e22ce' },
  unknown: { label: 'Unknown', hex: '#9ca3af' },
}

export function riskStyle(level: RiskLevel | null) {
  return RISK_STYLE[level ?? 'unknown']
}

/** [r, g, b] for deck.gl layers. */
export function riskRgb(level: RiskLevel | null): [number, number, number] {
  const hex = riskStyle(level).hex
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number]
}

export const FACTOR_LABEL = { wind: 'Wind', rain: 'Rain', snow: 'Snow' } as const
