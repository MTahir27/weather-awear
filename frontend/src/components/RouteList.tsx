import { memo } from 'react'

import type { TripPlan } from '../api/schemas'
import { routeName } from '../lib/routes'
import { CheckpointTable } from './CheckpointTable'
import { RecommendationBanner } from './RecommendationBanner'
import { RouteCard } from './RouteCard'

interface RouteListProps {
  plan: TripPlan
  selectedId: string
  onSelect: (routeId: string) => void
}

/** Memoised so scrubbing the forecast slider does not re-render the route cards. */
export const RouteList = memo(function RouteList({ plan, selectedId, onSelect }: RouteListProps) {
  const recommended = plan.routes.find((r) => r.id === plan.recommendation.route_id)
  const selected = plan.routes.find((r) => r.id === selectedId)
  return (
    <section aria-label="Route options" className="space-y-3">
      <RecommendationBanner
        recommendation={plan.recommendation}
        routeName={recommended ? routeName(recommended.rank) : ''}
      />
      {plan.routes.length < 3 && (
        <p className="text-xs text-slate-500">
          Only {plan.routes.length} distinct {plan.routes.length === 1 ? 'route' : 'routes'} found
          for this trip.
        </p>
      )}
      {plan.routes.map((route) => (
        <RouteCard
          key={route.id}
          route={route}
          name={routeName(route.rank)}
          selected={route.id === selectedId}
          onSelect={() => onSelect(route.id)}
        />
      ))}
      {selected && (
        <CheckpointTable key={selected.id} route={selected} name={routeName(selected.rank)} />
      )}
    </section>
  )
})
