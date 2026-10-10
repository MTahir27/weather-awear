import { useMutation, useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useCallback, useEffect, useState } from 'react'

import { ApiError, fetchHeatmap, planTrip } from './api/client'
import type { TripPlan, TripPlanRequest } from './api/schemas'
import { MapErrorBoundary } from './components/MapErrorBoundary'
import { RouteList } from './components/RouteList'
import { TimeControls, type MetricChoice } from './components/TimeControls'
import { TripForm } from './components/TripForm'
import { serverErrorsToForm } from './components/tripFormValidation'
import { formatTime } from './lib/format'
import { prepareHeatmap } from './lib/heatmap'
import { routeName } from './lib/routes'
import { truckProgressAt, truckStatusText } from './lib/truck'

const PLAYBACK_MS_PER_HOUR = 400

// The map (MapLibre + deck.gl) is the bulk of the bundle; load it separately.
const TripMap = lazy(() => import('./map/TripMap'))

function LoadingRoutes() {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <p className="text-sm text-slate-600">
        Finding routes and checking the forecast at every checkpoint… long trips can take ~10
        seconds.
      </p>
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-36 animate-pulse rounded-xl bg-slate-200" />
      ))}
    </div>
  )
}

function useHeatmap(plan: TripPlan | null) {
  return useQuery({
    queryKey: [
      'heatmap',
      plan?.departure_time,
      plan?.load_weight_lb,
      plan?.routes.map((r) => r.geometry),
    ],
    queryFn: async ({ signal }) => {
      if (!plan) throw new Error('No plan')
      const response = await fetchHeatmap(
        {
          routes: plan.routes.map((r) => r.geometry),
          departure_time: plan.departure_time,
          load_weight_lb: plan.load_weight_lb,
        },
        signal,
      )
      // Converted once; scrubbing then only indexes into typed arrays.
      return prepareHeatmap(response)
    },
    enabled: plan !== null,
    staleTime: Infinity,
  })
}

export default function App() {
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [frame, setFrame] = useState(0)
  const [metric, setMetric] = useState<MetricChoice>('risk')
  const [playing, setPlaying] = useState(false)

  const mutation = useMutation({
    mutationFn: (request: TripPlanRequest) => planTrip(request),
    onSuccess: (result) => {
      setPlan(result)
      setSelectedId(result.recommendation.route_id)
      setFrame(0)
      setPlaying(false)
    },
  })
  const heatmapQuery = useHeatmap(plan)
  const heatmap = heatmapQuery.data ?? null
  const frameCount = heatmap?.frameCount ?? 49

  // Playback advances one hour per tick and stops on the last frame.
  const isPlaying = playing && frame < frameCount - 1
  useEffect(() => {
    if (!isPlaying) return
    const timer = setTimeout(() => setFrame(frame + 1), PLAYBACK_MS_PER_HOUR)
    return () => clearTimeout(timer)
  }, [isPlaying, frame])
  const error = mutation.error
  const fieldErrors = error instanceof ApiError ? serverErrorsToForm(error.fieldErrors) : {}
  const hasFieldErrors = Object.keys(fieldErrors).length > 0

  const selectedRoute = plan?.routes.find((r) => r.id === selectedId)
  const departureMs = plan ? Date.parse(plan.departure_time) : 0
  const frameMs = heatmap?.frameMs ?? 3600_000
  const truckStatus =
    plan && selectedRoute
      ? truckStatusText({
          routeName: routeName(selectedRoute.rank),
          progress: truckProgressAt(selectedRoute, departureMs, departureMs + frame * frameMs),
          totalMiles: selectedRoute.distance_mi,
          arrivalIso: selectedRoute.arrival_time,
          windowEndMs: departureMs + (frameCount - 1) * frameMs,
          formatTime,
        })
      : undefined

  const selectRoute = useCallback((routeId: string) => setSelectedId(routeId), [])

  return (
    <div className="flex min-h-full flex-col lg:h-full lg:flex-row">
      <aside className="order-2 flex flex-col border-slate-200 bg-slate-50 lg:order-1 lg:h-full lg:w-[440px] lg:shrink-0 lg:overflow-y-auto lg:border-r">
        <header className="border-b border-slate-200 bg-white px-4 py-4 sm:px-6">
          <h1 className="text-lg font-semibold text-slate-900">Weather-Aware Truck Routing</h1>
          <p className="text-sm text-slate-600">
            Compare routes by forecast weather risk at the time you reach each stretch.
          </p>
        </header>

        <div className="space-y-6 px-4 py-5 sm:px-6">
          <TripForm
            onSubmit={(request) => mutation.mutate(request)}
            submitting={mutation.isPending}
            serverErrors={fieldErrors}
          />

          {error && !hasFieldErrors && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
            >
              {error.message}
            </div>
          )}

          {mutation.isPending ? (
            <LoadingRoutes />
          ) : (
            plan && <RouteList plan={plan} selectedId={selectedId} onSelect={selectRoute} />
          )}
        </div>
      </aside>

      <main className="relative order-1 h-[55vh] min-h-[320px] shrink-0 lg:order-2 lg:h-full lg:flex-1 lg:shrink">
        <MapErrorBoundary>
          <Suspense fallback={<div className="h-full w-full animate-pulse bg-slate-200" />}>
            <TripMap
              plan={plan}
              selectedId={selectedId}
              onSelectRoute={selectRoute}
              heatmap={heatmap}
              metric={metric}
              frame={frame}
            />
          </Suspense>
        </MapErrorBoundary>
        {!plan && !mutation.isPending && (
          <div className="pointer-events-none absolute inset-x-3 bottom-8 mx-auto max-w-sm rounded-xl bg-white/95 p-3 text-center text-sm text-slate-700 shadow-lg">
            Enter an origin, destination and load to compare routes by weather risk.
          </div>
        )}
        {plan && (
          <div className="absolute inset-x-2 bottom-2 mx-auto max-w-xl sm:inset-x-3 sm:bottom-8">
            <TimeControls
              departureMs={departureMs}
              frameMs={frameMs}
              frameCount={frameCount}
              frame={frame}
              onFrame={(next) => {
                setPlaying(false)
                setFrame(next)
              }}
              playing={isPlaying}
              onPlayingChange={setPlaying}
              metric={metric}
              onMetric={setMetric}
              status={heatmapQuery.isError ? 'error' : heatmap ? 'ready' : 'loading'}
              onRetry={() => void heatmapQuery.refetch()}
              truckStatus={truckStatus}
            />
          </div>
        )}
      </main>
    </div>
  )
}
