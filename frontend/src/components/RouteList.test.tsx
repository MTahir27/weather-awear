import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { tripPlanSchema, type TripPlan } from '../api/schemas'
import tripPlanFixture from '../test/fixtures/trip-plan.json'
import { riskSegments, routeName } from '../lib/routes'
import { RouteList } from './RouteList'

const PLAN: TripPlan = tripPlanSchema.parse(tripPlanFixture)

function blockedPlan(): TripPlan {
  const [first, ...rest] = PLAN.routes
  if (!first) throw new Error('fixture has no routes')
  return {
    ...PLAN,
    recommendation: {
      ...PLAN.recommendation,
      travel_advised: false,
      explanation: 'Every route crosses No Travel conditions at this departure time.',
    },
    routes: [
      {
        ...first,
        risk: {
          ...first.risk,
          miles_by_level: { ...first.risk.miles_by_level, no_travel: 12.5, low: 200 },
          unknown_mi: 3,
          worst_level: 'no_travel',
        },
        stops: [
          {
            kind: 'break',
            mile: 400,
            lat: 1,
            lon: 1,
            starts_at: PLAN.departure_time,
            ends_at: PLAN.departure_time,
          },
          {
            kind: 'rest',
            mile: 550,
            lat: 1,
            lon: 1,
            starts_at: PLAN.departure_time,
            ends_at: PLAN.departure_time,
          },
        ],
        traffic_delay_s: 1_200,
      },
      ...rest,
    ],
  }
}

describe('RouteList', () => {
  it('names routes A, B, C by rank', () => {
    expect([1, 2, 3].map(routeName)).toEqual(['Route A', 'Route B', 'Route C'])
  })

  it('explains the recommendation and marks the recommended route', () => {
    render(<RouteList plan={PLAN} selectedId="route-1" onSelect={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Recommended: Route A' })).toBeInTheDocument()
    expect(screen.getByText(PLAN.recommendation.explanation)).toBeInTheDocument()
    const cards = screen.getAllByRole('button')
    expect(cards).toHaveLength(3)
    expect(within(cards[0]!).getByText('Recommended')).toBeInTheDocument()
    expect(within(cards[1]!).queryByText('Recommended')).not.toBeInTheDocument()
  })

  it('shows distance and time for each route', () => {
    render(<RouteList plan={PLAN} selectedId="route-1" onSelect={vi.fn()} />)

    const first = screen.getAllByRole('button')[0]!
    expect(within(first).getByText('238 mi')).toBeInTheDocument()
    expect(within(first).getByText('Total time')).toBeInTheDocument()
  })

  it('reports selection state and lets the user switch routes', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<RouteList plan={PLAN} selectedId="route-1" onSelect={onSelect} />)

    const [first, second] = screen.getAllByRole('button')
    expect(first).toHaveAttribute('aria-pressed', 'true')
    expect(second).toHaveAttribute('aria-pressed', 'false')
    await user.click(second!)

    expect(onSelect).toHaveBeenCalledWith(PLAN.routes[1]!.id)
  })

  it('warns prominently when no route is advised', () => {
    render(<RouteList plan={blockedPlan()} selectedId="route-1" onSelect={vi.fn()} />)

    expect(screen.getByRole('alert')).toHaveTextContent('No safe route at this departure time')
  })

  it('says when a route is Low the whole way instead of listing zeros', () => {
    render(<RouteList plan={PLAN} selectedId="route-1" onSelect={vi.fn()} />)

    const first = screen.getAllByRole('button')[0]!
    expect(within(first).getByText('✓ Low risk the whole way')).toBeInTheDocument()
    expect(within(first).queryByText(/0 mi/)).not.toBeInTheDocument()
  })

  it('shows only the risk levels a route reaches, plus stops and traffic delay', () => {
    render(<RouteList plan={blockedPlan()} selectedId="route-1" onSelect={vi.fn()} />)

    const first = screen.getAllByRole('button')[0]!
    expect(within(first).getByText('12.5 mi')).toBeInTheDocument()
    expect(within(first).getByText('3 mi')).toBeInTheDocument() // unknown miles
    expect(within(first).queryByText('Severe:')).not.toBeInTheDocument()
    expect(
      within(first).getByText(/1 rest stop, 1 break · 20 min traffic delay/),
    ).toBeInTheDocument()
    expect(within(first).getByRole('img', { name: /No Travel 12.5 mi/ })).toBeInTheDocument()
  })

  it('notes when fewer than three routes exist', () => {
    render(
      <RouteList
        plan={{ ...PLAN, routes: PLAN.routes.slice(0, 1) }}
        selectedId="route-1"
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('Only 1 distinct route found for this trip.')).toBeInTheDocument()
  })
})

describe('riskSegments', () => {
  it('includes only levels with distance, plus unknown miles', () => {
    const segments = riskSegments({
      miles_by_level: { low: 10, moderate: 0, high: 2, severe: 0, no_travel: 0 },
      unknown_mi: 1,
      average: 0.3,
      worst_level: 'high',
    })

    expect(segments.map((s) => [s.key, s.miles])).toEqual([
      ['low', 10],
      ['high', 2],
      ['unknown', 1],
    ])
  })
})
