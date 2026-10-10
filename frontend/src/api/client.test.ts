import { afterEach, describe, expect, it, vi } from 'vitest'

import tripPlanFixture from '../test/fixtures/trip-plan.json'
import { ApiError, planTrip, searchPlaces } from './client'
import type { TripPlanRequest } from './schemas'

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

const REQUEST: TripPlanRequest = {
  origin: { lat: 32.7767, lon: -96.797 },
  destination: { lat: 29.7604, lon: -95.3698 },
  departure_time: '2030-01-01T08:00:00.000Z',
  load_weight_lb: 42_000,
  sample_interval_mi: 25,
  hours_of_service: true,
}

describe('planTrip', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts the request and parses a real backend response', async () => {
    const fetchSpy = mockFetch(200, tripPlanFixture)

    const plan = await planTrip(REQUEST)

    expect(plan.routes).toHaveLength(3)
    expect(plan.recommendation.route_id).toBe(plan.routes[0]?.id)
    const [url, init] = fetchSpy.mock.calls[0] ?? []
    expect(url).toBe('/api/trips/plan')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual(REQUEST)
  })

  it('rejects a response that does not match the schema', async () => {
    mockFetch(200, { routes: 'nope' })

    await expect(planTrip(REQUEST)).rejects.toThrow('unexpected response')
  })

  it('surfaces the server detail message', async () => {
    mockFetch(422, { detail: 'No truck route connects these locations.' })

    const error = await planTrip(REQUEST).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 422,
      message: 'No truck route connects these locations.',
    })
  })

  it('collects field validation errors, including nested ones', async () => {
    mockFetch(400, {
      departure_time: ['Departure time cannot be in the past.'],
      origin: { lat: ['Ensure this value is less than or equal to 90.'] },
    })

    const error = await planTrip(REQUEST).catch((e: unknown) => e)
    expect(error).toMatchObject({
      status: 400,
      fieldErrors: {
        departure_time: ['Departure time cannot be in the past.'],
        origin: ['Ensure this value is less than or equal to 90.'],
      },
    })
  })

  it('explains rate limiting', async () => {
    mockFetch(429, {})

    await expect(planTrip(REQUEST)).rejects.toThrow('Too many requests')
  })

  it('falls back to a generic message for unknown error bodies', async () => {
    mockFetch(500, { unexpected: 42 })

    await expect(planTrip(REQUEST)).rejects.toThrow('Request failed with status 500')
  })

  it('reports network failures in plain language', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(planTrip(REQUEST)).rejects.toMatchObject({
      status: 0,
      message: expect.stringContaining('Could not reach the server'),
    })
  })

  it('lets aborts propagate untouched', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new DOMException('aborted', 'AbortError'))

    await expect(planTrip(REQUEST)).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('searchPlaces', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('encodes the query and returns places', async () => {
    const fetchSpy = mockFetch(200, { results: [{ label: 'Dallas, TX', lat: 32.78, lon: -96.8 }] })

    const places = await searchPlaces('Dallas & Fort Worth')

    expect(places).toEqual([{ label: 'Dallas, TX', lat: 32.78, lon: -96.8 }])
    expect(fetchSpy.mock.calls[0]?.[0]).toBe('/api/geocode?q=Dallas+%26+Fort+Worth')
  })
})
