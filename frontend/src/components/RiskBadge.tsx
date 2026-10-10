import type { RiskLevel } from '../api/schemas'
import { riskStyle } from '../lib/risk'

export function RiskBadge({ level }: { level: RiskLevel | null }) {
  const style = riskStyle(level)
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
      <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: style.hex }} />
      {style.label}
    </span>
  )
}
