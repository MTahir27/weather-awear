import { memo } from 'react'
import { Marker } from 'react-map-gl/maplibre'

import { formatClock, formatDuration, formatMiles } from '../lib/format'
import { pointAtMile } from '../lib/geometry'
import { riskStyle } from '../lib/risk'
import { etaLabelCheckpoints, etaLabelSpacing, labelFraction, riskSummary } from '../lib/routes'
import type { MapRoute } from './layers'

// deck.gl's canvas is mounted in MapLibre's top-left control container
// (z-index 2), so labels need a higher z-index to render above it.
const LABEL_Z = 3

interface RouteLabelsProps {
  routes: MapRoute[]
  selectedId: string
  onSelectRoute: (routeId: string) => void
}

/**
 * A summary card on each route (name, distance, time, risk) and arrival-time
 * labels along the selected route. These are HTML markers rather than WebGL
 * text so they stay crisp, are keyboard-focusable and readable by screen
 * readers; memoised so scrubbing the forecast slider does not re-render them.
 */
export const RouteLabels = memo(function RouteLabels({
  routes,
  selectedId,
  onSelectRoute,
}: RouteLabelsProps) {
  const selected = routes.find((r) => r.route.id === selectedId)
  return (
    <>
      {selected &&
        etaLabelCheckpoints(
          selected.route.checkpoints,
          etaLabelSpacing(selected.route.distance_mi),
        ).map((checkpoint) => (
          <Marker
            key={`eta-${checkpoint.mile}`}
            longitude={checkpoint.lon}
            latitude={checkpoint.lat}
            anchor="left"
            offset={[9, 0]}
            style={{ pointerEvents: 'none', zIndex: LABEL_Z }}
          >
            <span className="hidden rounded bg-slate-900/85 px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap text-white shadow sm:inline-block">
              {formatClock(checkpoint.eta)}
            </span>
          </Marker>
        ))}

      {routes.map(({ route, name, path }) => {
        const [longitude, latitude] = pointAtMile(
          path,
          route.distance_mi,
          route.distance_mi * labelFraction(route.rank),
        )
        const isSelected = route.id === selectedId
        const risk = riskSummary(route.risk)
        const worst = riskStyle(route.risk.worst_level)
        return (
          <Marker
            key={route.id}
            longitude={longitude}
            latitude={latitude}
            anchor="bottom"
            offset={[0, -10]}
            style={{ zIndex: isSelected ? LABEL_Z + 1 : LABEL_Z }}
          >
            <button
              type="button"
              onClick={() => onSelectRoute(route.id)}
              aria-pressed={isSelected}
              aria-label={`${name}${route.recommended ? ' (recommended)' : ''}: ${formatMiles(
                route.distance_mi,
              )}, ${formatDuration(route.duration_s)}, ${risk}`}
              className={`rounded-lg border px-2 py-1 text-left text-[11px] leading-tight shadow-md transition focus:ring-2 focus:ring-sky-500 focus:outline-none ${
                isSelected
                  ? 'border-sky-500 bg-white text-slate-900'
                  : 'border-slate-200 bg-white/90 text-slate-700 hover:bg-white'
              }`}
            >
              <span className="flex items-center gap-1 font-semibold">
                {name}
                {route.recommended && (
                  <span className="rounded bg-sky-600 px-1 text-[10px] font-semibold text-white">
                    Recommended
                  </span>
                )}
              </span>
              <span className="block whitespace-nowrap">
                {formatMiles(route.distance_mi)} · {formatDuration(route.duration_s)}
              </span>
              <span className="flex items-center gap-1 whitespace-nowrap">
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: worst.hex }}
                />
                {risk}
              </span>
            </button>
          </Marker>
        )
      })}
    </>
  )
})
