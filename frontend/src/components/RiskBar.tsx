import type { Route } from '../api/schemas'
import { formatMiles } from '../lib/format'
import { riskSegments } from '../lib/routes'

/** Stacked bar of the route's miles at each risk level. */
export function RiskBar({ risk }: { risk: Route['risk'] }) {
  const segments = riskSegments(risk)
  const total = segments.reduce((sum, s) => sum + s.miles, 0)
  const description = segments.map((s) => `${s.label} ${formatMiles(s.miles)}`).join(', ')

  return (
    <div
      role="img"
      aria-label={`Risk by distance: ${description}`}
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-200"
    >
      {segments.map((segment) => (
        <div
          key={segment.key}
          title={`${segment.label}: ${formatMiles(segment.miles)}`}
          style={{ width: `${(segment.miles / total) * 100}%`, backgroundColor: segment.hex }}
        />
      ))}
    </div>
  )
}
