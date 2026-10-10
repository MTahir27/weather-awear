import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as client from '../api/client'
import { renderWithQuery } from '../test/render'
import { TripForm } from './TripForm'

describe('TripForm', () => {
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

  it('shows every validation error instead of submitting an empty form', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithQuery(<TripForm onSubmit={onSubmit} submitting={false} />)

    await user.click(screen.getByRole('button', { name: 'Find the safest route' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Choose an origin from the suggestions.')).toBeInTheDocument()
    expect(screen.getByText('Choose a destination from the suggestions.')).toBeInTheDocument()
    expect(screen.getByText('Enter the load weight.')).toBeInTheDocument()
  })

  it('submits a complete trip request', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    renderWithQuery(<TripForm onSubmit={onSubmit} submitting={false} />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Dallas')
    await user.click(await screen.findByRole('option', { name: 'Dallas, TX' }))
    await user.type(screen.getByRole('combobox', { name: 'Destination' }), 'Houston')
    await user.click(await screen.findByRole('option', { name: 'Houston, TX' }))
    await user.type(screen.getByLabelText('Load weight (lb)'), '42000')
    await user.click(screen.getByRole('radio', { name: '50 mi' }))
    await user.click(screen.getByRole('checkbox', { name: /Include driver rest stops/ }))
    await user.click(screen.getByRole('button', { name: 'Find the safest route' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0]?.[0]).toMatchObject({
      origin: { lat: 32.78, lon: -96.8 },
      destination: { lat: 29.76, lon: -95.37 },
      load_weight_lb: 42_000,
      sample_interval_mi: 50,
      hours_of_service: false,
    })
  })

  it('clears a field error as soon as the field is edited', async () => {
    const user = userEvent.setup()
    renderWithQuery(<TripForm onSubmit={vi.fn()} submitting={false} />)

    await user.click(screen.getByRole('button', { name: 'Find the safest route' }))
    await user.type(screen.getByLabelText('Load weight (lb)'), '1')

    expect(screen.queryByText('Enter the load weight.')).not.toBeInTheDocument()
  })

  it('shows server-side errors and a busy state while submitting', () => {
    renderWithQuery(
      <TripForm
        onSubmit={vi.fn()}
        submitting
        serverErrors={{ departure: 'Departure time cannot be in the past.' }}
      />,
    )

    expect(screen.getByText('Departure time cannot be in the past.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Checking routes and weather…' })).toBeDisabled()
  })
})
