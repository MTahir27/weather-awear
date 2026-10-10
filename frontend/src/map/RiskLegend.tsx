import { RISK_STYLE } from '../lib/risk'

export function RiskLegend() {
  return (
    <div className="absolute bottom-8 left-3 rounded-lg bg-white/95 px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-semibold text-slate-700">Checkpoint risk</p>
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
      </ul>
    </div>
  )
}
