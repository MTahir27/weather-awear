import { formatTime } from '../lib/format'
import { HEATMAP_METRICS, METRIC_LABEL, type HeatmapMetric } from '../lib/heatmap'

export type MetricChoice = HeatmapMetric | 'off'

interface TimeControlsProps {
  departureMs: number
  frameMs: number
  frameCount: number
  frame: number
  onFrame: (frame: number) => void
  playing: boolean
  onPlayingChange: (playing: boolean) => void
  metric: MetricChoice
  onMetric: (metric: MetricChoice) => void
  status: 'loading' | 'error' | 'ready'
  onRetry: () => void
  /** Where the selected route's truck is at this time (see truckStatusText). */
  truckStatus?: string
}

const CHOICES: MetricChoice[] = [...HEATMAP_METRICS, 'off']

export function TimeControls({
  departureMs,
  frameMs,
  frameCount,
  frame,
  onFrame,
  playing,
  onPlayingChange,
  metric,
  onMetric,
  status,
  onRetry,
  truckStatus,
}: TimeControlsProps) {
  const hours = Math.round((frame * frameMs) / 3600_000)
  const time = formatTime(new Date(departureMs + frame * frameMs).toISOString())
  const label = hours === 0 ? `Departure · ${time}` : `+${hours} h · ${time}`

  return (
    <div className="rounded-xl bg-white/95 p-3 shadow-lg backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (playing) {
              onPlayingChange(false)
              return
            }
            if (frame >= frameCount - 1) onFrame(0)
            onPlayingChange(true)
          }}
          disabled={status !== 'ready'}
          aria-label={playing ? 'Pause' : 'Play forecast'}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-600 text-white shadow focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:outline-none disabled:opacity-50"
        >
          {playing ? (
            <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4 fill-current">
              <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
            </svg>
          ) : (
            <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4 fill-current">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <label htmlFor="forecast-hour" className="font-semibold text-slate-800">
              Forecast time
            </label>
            <span className="truncate text-slate-600">{label}</span>
          </div>
          <input
            id="forecast-hour"
            type="range"
            min={0}
            max={Math.max(frameCount - 1, 0)}
            step={1}
            value={frame}
            disabled={status !== 'ready'}
            onChange={(event) => onFrame(Number(event.target.value))}
            aria-valuetext={`${hours} hours after departure, ${time}`}
            className="mt-1 w-full accent-sky-600"
          />
          {truckStatus && (
            <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-600">
              <span aria-hidden className="h-2 w-2 shrink-0 rounded-full bg-sky-600" />
              <span>{truckStatus}</span>
            </p>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div role="radiogroup" aria-label="Heatmap layer" className="flex flex-wrap gap-1">
          {CHOICES.map((choice) => (
            <button
              key={choice}
              type="button"
              role="radio"
              aria-checked={metric === choice}
              onClick={() => onMetric(choice)}
              className={`rounded-md px-2 py-1 text-xs font-medium focus:ring-2 focus:ring-sky-500 focus:outline-none ${
                metric === choice
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {choice === 'off' ? 'Off' : METRIC_LABEL[choice]}
            </button>
          ))}
        </div>
        {status === 'loading' && (
          <span role="status" className="text-xs text-slate-500">
            Loading weather layer…
          </span>
        )}
        {status === 'error' && (
          <span role="alert" className="text-xs text-red-700">
            Weather layer unavailable.{' '}
            <button type="button" onClick={onRetry} className="font-semibold underline">
              Retry
            </button>
          </span>
        )}
      </div>
    </div>
  )
}
