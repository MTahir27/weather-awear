import { describe, expect, it } from 'vitest'

import type { Route } from '../api/schemas'
import { pointAtMile } from './geometry'
import { truckProgressAt, truckStatusText } from './truck'

const H = 3600_000
const DEPART = Date.UTC(2030, 0, 1, 8)
const iso = (ms: number) => new Date(ms).toISOString()

function checkpoint(mile: number, etaMs: number) {
  return {
    mile,
    lat: 0,
    lon: 0,
    eta: iso(etaMs),
    level: 'low' as const,
    wind_mph: 5,
    gust_mph: 8,
    rain_in_per_hr: 0,
    snow_in_per_hr: 0,
    drivers: [],
    load_escalated: false,
  }
}

// 0-100 mi in 2 h, a 10 h rest at mile 100, then 100-150 mi in 1 h.
const ROUTE = {
  distance_mi: 150,
  arrival_time: iso(DEPART + 13 * H),
  checkpoints: [
    checkpoint(0, DEPART),
    checkpoint(50, DEPART + H),
    checkpoint(100, DEPART + 2 * H),
    checkpoint(150, DEPART + 13 * H),
  ],
  stops: [
    {
      kind: 'rest' as const,
      mile: 100,
      lat: 0,
      lon: 0,
      starts_at: iso(DEPART + 2 * H),
      ends_at: iso(DEPART + 12 * H),
    },
  ],
} as unknown as Route

describe('truckProgressAt', () => {
  it.each([
    [-1, 0, 'waiting'],
    [0, 0, 'driving'],
    [0.5, 25, 'driving'],
    [1.5, 75, 'driving'],
    [2, 100, 'resting'],
    [7, 100, 'resting'],
    [12.5, 125, 'driving'],
    [13, 150, 'arrived'],
    [40, 150, 'arrived'],
  ])('%s h after departure -> mile %s (%s)', (hours, mile, status) => {
    const progress = truckProgressAt(ROUTE, DEPART, DEPART + hours * H)

    expect(progress.mile).toBeCloseTo(mile)
    expect(progress.status).toBe(status)
  })
})

describe('pointAtMile', () => {
  const path: [number, number][] = [
    [-100, 40],
    [-100, 41],
  ]

  it('interpolates along the scaled path', () => {
    expect(pointAtMile(path, 100, 50)[1]).toBeCloseTo(40.5)
  })

  it('clamps to the ends', () => {
    expect(pointAtMile(path, 100, -5)).toEqual(path[0])
    expect(pointAtMile(path, 100, 500)).toEqual(path[1])
  })

  it('rejects an empty path', () => {
    expect(() => pointAtMile([], 1, 0)).toThrow('empty')
  })
})

describe('truckStatusText', () => {
  const base = {
    routeName: 'Route A',
    totalMiles: 3135,
    arrivalIso: '2030-01-04T17:00:00Z',
    windowEndMs: Date.UTC(2030, 0, 3, 8),
    formatTime: () => 'Fri 5:00 PM',
  }

  it('explains a truck still on the road when the slider window ends', () => {
    expect(truckStatusText({ ...base, progress: { mile: 1240.4, status: 'driving' } })).toBe(
      'Route A truck: driving · mile 1,240 of 3,135 · arrives Fri 5:00 PM (after the 48 h forecast window)',
    )
  })

  it('describes stops, waiting and arrival', () => {
    const inWindow = { ...base, windowEndMs: Date.UTC(2030, 0, 9) }

    expect(truckStatusText({ ...inWindow, progress: { mile: 550, status: 'resting' } })).toBe(
      'Route A truck: stopped for a break or rest · mile 550 of 3,135 · arrives Fri 5:00 PM',
    )
    expect(truckStatusText({ ...inWindow, progress: { mile: 0, status: 'waiting' } })).toBe(
      'Route A truck: not departed yet · arrives Fri 5:00 PM',
    )
    expect(truckStatusText({ ...inWindow, progress: { mile: 3135, status: 'arrived' } })).toBe(
      'Route A truck: arrived Fri 5:00 PM',
    )
  })
})
