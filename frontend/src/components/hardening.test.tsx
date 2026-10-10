import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { tripPlanSchema } from '../api/schemas'
import tripPlanFixture from '../test/fixtures/trip-plan.json'
import { CheckpointTable } from './CheckpointTable'
import { MapErrorBoundary } from './MapErrorBoundary'

const PLAN = tripPlanSchema.parse(tripPlanFixture)

describe('CheckpointTable', () => {
  it('lists every checkpoint with its arrival, risk and forecast', async () => {
    const user = userEvent.setup()
    const route = PLAN.routes[0]!
    render(<CheckpointTable route={route} name="Route A" />)

    await user.click(screen.getByText(`Route A: all ${route.checkpoints.length} checkpoints`))

    const rows = within(screen.getByRole('table')).getAllByRole('row')
    expect(rows).toHaveLength(route.checkpoints.length + 1) // plus header
    expect(within(rows[2]!).getByText('25')).toBeInTheDocument()
  })

  it('shows causes, load escalation and missing data explicitly', async () => {
    const user = userEvent.setup()
    const base = PLAN.routes[0]!
    const route = {
      ...base,
      checkpoints: [
        {
          ...base.checkpoints[0]!,
          level: 'no_travel' as const,
          drivers: ['wind' as const],
          load_escalated: true,
        },
        { ...base.checkpoints[1]!, level: null, wind_mph: null, rain_in_per_hr: null },
      ],
    }
    render(<CheckpointTable route={route} name="Route A" />)
    await user.click(screen.getByText(/all 2 checkpoints/))

    expect(screen.getByText('Wind + heavy load')).toBeInTheDocument()
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.getAllByText(/—/).length).toBeGreaterThan(0)
  })
})

describe('MapErrorBoundary', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('replaces a crashed map with an explanation', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    function Broken(): never {
      throw new Error('WebGL context lost')
    }

    render(
      <MapErrorBoundary>
        <Broken />
      </MapErrorBoundary>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('The map could not be displayed')
  })

  it('renders the map when nothing fails', () => {
    render(
      <MapErrorBoundary>
        <p>map</p>
      </MapErrorBoundary>,
    )

    expect(screen.getByText('map')).toBeInTheDocument()
  })
})
