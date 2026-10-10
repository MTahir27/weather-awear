import type { Route } from '../api/schemas'
import { formatTime } from '../lib/format'
import { FACTOR_LABEL } from '../lib/risk'
import { RiskBadge } from './RiskBadge'

function amount(value: number | null, unit: string, digits: number): string {
  return value === null ? '—' : `${value.toFixed(digits)}${unit}`
}

/** Every checkpoint of a route as a table, so the details do not depend on map hover. */
export function CheckpointTable({ route, name }: { route: Route; name: string }) {
  return (
    <details className="rounded-xl border border-slate-200 bg-white">
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-800">
        {name}: all {route.checkpoints.length} checkpoints
      </summary>
      <div className="max-h-96 overflow-auto border-t border-slate-200">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">
            Checkpoints along {name} with arrival time, risk and forecast
          </caption>
          <thead className="sticky top-0 bg-slate-50 text-slate-600">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">
                Mile
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Arrival
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Risk
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Wind / gust (mph)
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Rain / snow (in/hr)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {route.checkpoints.map((c) => (
              <tr key={c.mile}>
                <td className="px-3 py-1.5 tabular-nums">{Math.round(c.mile)}</td>
                <td className="px-3 py-1.5 whitespace-nowrap">{formatTime(c.eta)}</td>
                <td className="px-3 py-1.5">
                  <RiskBadge level={c.level} />
                  {c.drivers.length > 0 && (
                    <span className="mt-0.5 block text-[11px] text-slate-500">
                      {c.drivers.map((d) => FACTOR_LABEL[d]).join(' + ')}
                      {c.load_escalated && ' + heavy load'}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5 tabular-nums">
                  {amount(c.wind_mph, '', 0)} / {amount(c.gust_mph, '', 0)}
                </td>
                <td className="px-3 py-1.5 tabular-nums">
                  {amount(c.rain_in_per_hr, '', 2)} / {amount(c.snow_in_per_hr, '', 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
