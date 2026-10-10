import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as client from '../api/client'
import type { Place } from '../api/schemas'
import { renderWithQuery } from '../test/render'
import { PlaceInput } from './PlaceInput'

const PLACES: Place[] = [
  { label: 'Denver, CO', lat: 39.74, lon: -104.99 },
  { label: 'Denver, NC', lat: 35.53, lon: -81.03 },
]

function Harness({ onChange }: { onChange: (place: Place | null) => void }) {
  const [value, setValue] = useState<Place | null>(null)
  return (
    <PlaceInput
      label="Origin"
      value={value}
      onChange={(place) => {
        setValue(place)
        onChange(place)
      }}
    />
  )
}

describe('PlaceInput', () => {
  let search: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    search = vi.spyOn(client, 'searchPlaces').mockResolvedValue(PLACES)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('debounces typing into a single search and lists suggestions', async () => {
    const user = userEvent.setup()
    renderWithQuery(<Harness onChange={vi.fn()} />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Denver')

    expect(await screen.findByRole('option', { name: 'Denver, CO' })).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveAttribute('aria-expanded', 'true')
    expect(search).toHaveBeenCalledTimes(1)
    expect(search).toHaveBeenCalledWith('Denver', expect.any(AbortSignal))
  })

  it('selects a suggestion with the keyboard', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithQuery(<Harness onChange={onChange} />)
    const input = screen.getByRole('combobox', { name: 'Origin' })

    await user.type(input, 'Denver')
    await screen.findByRole('option', { name: 'Denver, CO' })
    await user.keyboard('{ArrowDown}{ArrowDown}')
    expect(input).toHaveAttribute('aria-activedescendant', expect.stringContaining('-1'))
    await user.keyboard('{Enter}')

    expect(onChange).toHaveBeenLastCalledWith(PLACES[1])
    expect(input).toHaveValue('Denver, NC')
    expect(input).toHaveAttribute('aria-expanded', 'false')
  })

  it('selects a suggestion with the mouse', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithQuery(<Harness onChange={onChange} />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Denver')
    await user.click(await screen.findByRole('option', { name: 'Denver, CO' }))

    expect(onChange).toHaveBeenLastCalledWith(PLACES[0])
  })

  it('clears the selection when the text is edited', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithQuery(<Harness onChange={onChange} />)
    const input = screen.getByRole('combobox', { name: 'Origin' })

    await user.type(input, 'Denver')
    await user.click(await screen.findByRole('option', { name: 'Denver, CO' }))
    await user.type(input, 'x')

    expect(onChange).toHaveBeenLastCalledWith(null)
  })

  it('does not search for a single character', async () => {
    const user = userEvent.setup()
    renderWithQuery(<Harness onChange={vi.fn()} />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'D')
    await new Promise((resolve) => setTimeout(resolve, 400))

    expect(search).not.toHaveBeenCalled()
  })

  it('tells the user when nothing matches', async () => {
    search.mockResolvedValue([])
    const user = userEvent.setup()
    renderWithQuery(<Harness onChange={vi.fn()} />)

    await user.type(screen.getByRole('combobox', { name: 'Origin' }), 'Atlantis')

    expect(await screen.findByText('No matching places in the US or Canada.')).toBeInTheDocument()
  })

  it('closes the list on Escape', async () => {
    const user = userEvent.setup()
    renderWithQuery(<Harness onChange={vi.fn()} />)
    const input = screen.getByRole('combobox', { name: 'Origin' })

    await user.type(input, 'Denver')
    await screen.findByRole('option', { name: 'Denver, CO' })
    await user.keyboard('{Escape}')

    await waitFor(() => expect(input).toHaveAttribute('aria-expanded', 'false'))
  })

  it('shows a validation error accessibly', () => {
    renderWithQuery(<PlaceInput label="Origin" value={null} onChange={vi.fn()} error="Required" />)

    const input = screen.getByRole('combobox', { name: 'Origin' })
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Required')
  })
})
