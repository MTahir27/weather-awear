import type { TripPlan } from '../api/schemas'

export function RecommendationBanner({
  recommendation,
  routeName,
}: {
  recommendation: TripPlan['recommendation']
  routeName: string
}) {
  if (!recommendation.travel_advised) {
    return (
      <div role="alert" className="rounded-xl border border-purple-300 bg-purple-50 p-4">
        <h2 className="font-semibold text-purple-900">No safe route at this departure time</h2>
        <p className="mt-1 text-sm text-purple-900">{recommendation.explanation}</p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50 p-4">
      <h2 className="font-semibold text-sky-900">Recommended: {routeName}</h2>
      <p className="mt-1 text-sm text-sky-900">{recommendation.explanation}</p>
    </div>
  )
}
