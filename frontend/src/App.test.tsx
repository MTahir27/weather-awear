import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import * as client from './api/client'
import { tripPlanSchema } from './api/schemas'
import tripPlanFixture from './test/fixtures/trip-plan.json'
import { renderWithQuery } from './test/render'

// WebGL is unavailable in jsdom; the map is covered by its own layer tests.
vi.mock('./map/TripMap', () => ({
  default: ({ selectedId }: { selectedId: string }) => (
    <div data-testid="map">selected: {selectedId}</div>
  ),
}))

const PLAN = tripPlanSchema.parse(tripPlanFixture)

async function fillAndSubmit() {
  const user = userEvent.setup()
  await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Dallas')
  await user.click(await screen.findByRole('option', { name: 'Dallas, TX' }))
  await user.type(screen.getByRole('combobox', { name: 'Destination' }), 'Houston')
  await user.click(await screen.findByRole('option', { name: 'Houston, TX' }))
  await user.type(screen.getByLabelText('Load weight (lb)'), '42000')
  await user.click(screen.getByRole('button', { name: 'Find the safest route' }))
  return user
}

describe('App', () => {
  beforeEach(() => {
    vi.spyOn(client, 'searchPlaces').mockImplementation(async (query) =>
      query.toLowerCase().startsWith('dal')
        ? [{ label: 'Dallas, TX', lat: 32.78, lon: -96.8 }]
        : [{ label: 'Houston, TX', lat: 29.76, lon: -95.37 }],
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('plans a trip and selects the recommended route', async () => {
    vi.spyOn(client, 'planTrip').mockResolvedValue(PLAN)
    renderWithQuery(<App />)

    const user = await fillAndSubmit()

    expect(await screen.findByRole('heading', { name: 'Recommended: Route A' })).toBeInTheDocument()
    expect(await screen.findByTestId('map')).toHaveTextContent(`selected: ${PLAN.routes[0]!.id}`)

    await user.click(screen.getAllByRole('button', { name: /Route B/ })[0]!)
    expect(screen.getByTestId('map')).toHaveTextContent(`selected: ${PLAN.routes[1]!.id}`)
  })

  it('shows a loading state while planning', async () => {
    vi.spyOn(client, 'planTrip').mockReturnValue(new Promise(() => {}))
    renderWithQuery(<App />)

    await fillAndSubmit()

    expect(screen.getByRole('status')).toHaveTextContent('Finding routes')
    expect(screen.getByRole('button', { name: 'Checking routes and weather…' })).toBeDisabled()
  })

  it('shows a service error message', async () => {
    vi.spyOn(client, 'planTrip').mockRejectedValue(
      new client.ApiError(422, 'No truck route connects these locations.'),
    )
    renderWithQuery(<App />)

    await fillAndSubmit()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No truck route connects these locations.',
    )
  })

  it('shows server field errors next to the fields', async () => {
    vi.spyOn(client, 'planTrip').mockRejectedValue(
      new client.ApiError(400, 'Please correct the highlighted fields.', {
        departure_time: ['Departure time cannot be in the past.'],
      }),
    )
    renderWithQuery(<App />)

    await fillAndSubmit()

    expect(await screen.findByText('Departure time cannot be in the past.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
