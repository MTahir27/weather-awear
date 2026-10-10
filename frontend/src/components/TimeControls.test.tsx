import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { TimeControls } from './TimeControls'

const DEPART = Date.UTC(2030, 0, 1, 8)

function setup(overrides: Partial<Parameters<typeof TimeControls>[0]> = {}) {
  const props = {
    departureMs: DEPART,
    frameMs: 3600_000,
    frameCount: 49,
    frame: 0,
    onFrame: vi.fn(),
    playing: false,
    onPlayingChange: vi.fn(),
    metric: 'risk' as const,
    onMetric: vi.fn(),
    status: 'ready' as const,
    onRetry: vi.fn(),
    ...overrides,
  }
  render(<TimeControls {...props} />)
  return props
}

describe('TimeControls', () => {
  it('labels the departure frame and later frames by offset', () => {
    setup()
    expect(screen.getByText(/^Departure ·/)).toBeInTheDocument()
  })

  it('describes the selected hour for assistive technology', () => {
    setup({ frame: 6 })

    const slider = screen.getByRole('slider', { name: 'Forecast time' })
    expect(slider).toHaveValue('6')
    expect(slider).toHaveAttribute('max', '48')
    expect(slider.getAttribute('aria-valuetext')).toMatch(/^6 hours after departure/)
    expect(screen.getByText(/^\+6 h ·/)).toBeInTheDocument()
  })

  it('reports slider changes', () => {
    const props = setup()

    fireEvent.change(screen.getByRole('slider'), { target: { value: '12' } })

    expect(props.onFrame).toHaveBeenCalledWith(12)
  })

  it('plays, pauses, and restarts from the beginning at the end', async () => {
    const user = userEvent.setup()
    const atEnd = setup({ frame: 48 })

    await user.click(screen.getByRole('button', { name: 'Play forecast' }))

    expect(atEnd.onFrame).toHaveBeenCalledWith(0)
    expect(atEnd.onPlayingChange).toHaveBeenCalledWith(true)
  })

  it('pauses while playing', async () => {
    const user = userEvent.setup()
    const props = setup({ playing: true, frame: 3 })

    await user.click(screen.getByRole('button', { name: 'Pause' }))

    expect(props.onPlayingChange).toHaveBeenCalledWith(false)
    expect(props.onFrame).not.toHaveBeenCalled()
  })

  it('switches the heatmap layer', async () => {
    const user = userEvent.setup()
    const props = setup()

    expect(screen.getByRole('radio', { name: 'Overall risk' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    await user.click(screen.getByRole('radio', { name: 'Snow' }))
    await user.click(screen.getByRole('radio', { name: 'Off' }))

    expect(props.onMetric).toHaveBeenNthCalledWith(1, 'snow')
    expect(props.onMetric).toHaveBeenNthCalledWith(2, 'off')
  })

  it('disables playback while loading and offers a retry on error', async () => {
    const user = userEvent.setup()
    setup({ status: 'loading' })
    expect(screen.getByRole('slider')).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Loading weather layer')

    const props = setup({ status: 'error' })
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(props.onRetry).toHaveBeenCalled()
  })
})

describe('TimeControls truck status', () => {
  it('shows where the selected truck is', () => {
    setup({ truckStatus: 'Route A truck: driving · mile 1,240 of 3,135' })

    expect(screen.getByText('Route A truck: driving · mile 1,240 of 3,135')).toBeInTheDocument()
  })
})
