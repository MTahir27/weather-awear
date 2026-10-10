import { RISK_STYLE } from '../lib/risk'

function LegendItems() {
  return (
    <ul className="space-y-0.5">
      {Object.entries(RISK_STYLE).map(([key, style]) => (
        <li key={key} className="flex items-center gap-2 text-slate-700">
          <span
            aria-hidden
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: style.hex }}
          />
          {style.label}
        </li>
      ))}
      <li className="flex items-center gap-2 text-slate-700">
        <span
          aria-hidden
          className="h-2.5 w-2.5 rounded-full border-2 border-white bg-slate-900 ring-1 ring-slate-300"
        />
        Rest stop / break
      </li>
      <li className="flex items-center gap-2 text-slate-700">
        <span
          aria-hidden
          className="h-3 w-3 rounded-full border-2 border-white bg-sky-600 ring-1 ring-slate-300"
        />
        Truck at forecast time
      </li>
    </ul>
  )
}

/** Full legend on large screens; a collapsed toggle on phones so it does not cover the map. */
export function RiskLegend() {
  return (
    <>
      <div className="absolute top-3 left-3 hidden rounded-lg bg-white/95 px-3 py-2 text-xs shadow-md lg:block">
        <p className="mb-1 font-semibold text-slate-700">Risk levels</p>
        <LegendItems />
      </div>
      <details className="absolute top-3 left-3 rounded-lg bg-white/95 px-3 py-2 text-xs shadow-md lg:hidden">
        <summary className="cursor-pointer font-semibold text-slate-700">Legend</summary>
        <div className="mt-1">
          <LegendItems />
        </div>
      </details>
    </>
  )
}
