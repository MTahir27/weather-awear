import type { Route } from '../api/schemas'
import { formatDuration, formatMiles, formatTime } from '../lib/format'
import { riskStyle } from '../lib/risk'
import { riskBreakdown } from '../lib/routes'
import { RiskBadge } from './RiskBadge'
import { RiskBar } from './RiskBar'

interface RouteCardProps {
  route: Route
  name: string
  selected: boolean
  onSelect: () => void
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  )
}

export function RouteCard({ route, name, selected, onSelect }: RouteCardProps) {
  const restStops = route.stops.filter((s) => s.kind === 'rest').length
  const breaks = route.stops.length - restStops
  const breakdown = riskBreakdown(route.risk)

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-xl border bg-white p-4 text-left shadow-sm transition focus:ring-2 focus:ring-sky-500 focus:outline-none ${
        selected ? 'border-sky-500 ring-1 ring-sky-500' : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-900">{name}</h3>
          <p className="text-xs text-slate-500">Arrives {formatTime(route.arrival_time)}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          {route.recommended && (
            <span className="rounded-full bg-sky-600 px-2 py-0.5 text-xs font-semibold text-white">
              Recommended
            </span>
          )}
          <RiskBadge level={route.risk.worst_level} />
        </div>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-2">
        <Stat label="Distance" value={formatMiles(route.distance_mi)} />
        <Stat label="Total time" value={formatDuration(route.duration_s)} />
        <Stat label="Driving" value={formatDuration(route.driving_s)} />
      </dl>

      <div className="mt-3">
        <RiskBar risk={route.risk} />
        {breakdown.length === 0 ? (
          <p className="mt-2 text-xs font-medium text-green-700">✓ Low risk the whole way</p>
        ) : (
          <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
            {breakdown.map((item) => (
              <li key={item.key} className="flex items-center gap-1">
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-full"
                  style={{
                    backgroundColor: riskStyle(item.key === 'unknown' ? null : item.key).hex,
                  }}
                />
                {item.label}:{' '}
                <span className="font-semibold text-slate-800">{formatMiles(item.miles)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(route.stops.length > 0 || route.traffic_delay_s > 60) && (
        <p className="mt-2 text-xs text-slate-500">
          {route.stops.length > 0 &&
            `${restStops} rest ${restStops === 1 ? 'stop' : 'stops'}, ${breaks} ${
              breaks === 1 ? 'break' : 'breaks'
            }`}
          {route.stops.length > 0 && route.traffic_delay_s > 60 && ' · '}
          {route.traffic_delay_s > 60 && `${formatDuration(route.traffic_delay_s)} traffic delay`}
        </p>
      )}
    </button>
  )
}
