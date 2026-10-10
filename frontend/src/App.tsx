import { useMutation } from '@tanstack/react-query'
import { lazy, Suspense, useCallback, useState } from 'react'

import { ApiError, planTrip } from './api/client'
import type { TripPlan, TripPlanRequest } from './api/schemas'
import { RouteList } from './components/RouteList'
import { TripForm } from './components/TripForm'
import { serverErrorsToForm } from './components/tripFormValidation'

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

export default function App() {
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [selectedId, setSelectedId] = useState('')

  const mutation = useMutation({
    mutationFn: (request: TripPlanRequest) => planTrip(request),
    onSuccess: (result) => {
      setPlan(result)
      setSelectedId(result.recommendation.route_id)
    },
  })
  const error = mutation.error
  const fieldErrors = error instanceof ApiError ? serverErrorsToForm(error.fieldErrors) : {}
  const hasFieldErrors = Object.keys(fieldErrors).length > 0

  const selectRoute = useCallback((routeId: string) => setSelectedId(routeId), [])

  return (
    <div className="flex h-full flex-col lg:flex-row">
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

      <main className="order-1 h-[45vh] min-h-[280px] lg:order-2 lg:h-full lg:flex-1">
        <Suspense fallback={<div className="h-full w-full animate-pulse bg-slate-200" />}>
          <TripMap plan={plan} selectedId={selectedId} onSelectRoute={selectRoute} />
        </Suspense>
      </main>
    </div>
  )
}
