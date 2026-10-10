import { describe, expect, it } from 'vitest'

import {
  defaultDeparture,
  formatDuration,
  formatMiles,
  fromDateTimeLocal,
  toDateTimeLocal,
} from './format'

describe('formatDuration', () => {
  it.each([
    [0, '0 min'],
    [59 * 60, '59 min'],
    [3600, '1 h'],
    [3600 + 29 * 60 + 40, '1 h 30 min'],
    [24.2 * 3600, '24 h 12 min'],
    [-10, '0 min'],
  ])('%s s -> %s', (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected)
  })
})

describe('formatMiles', () => {
  it.each([
    [0, '0 mi'],
    [12.345, '12.3 mi'],
    [238.48, '238 mi'],
    [1006.08, '1,006 mi'],
  ])('%s -> %s', (miles, expected) => {
    expect(formatMiles(miles)).toBe(expected)
  })
})

describe('datetime-local conversion', () => {
  it('round-trips a local time', () => {
    const date = new Date(2030, 0, 5, 7, 30)

    expect(toDateTimeLocal(date)).toBe('2030-01-05T07:30')
    expect(fromDateTimeLocal('2030-01-05T07:30')?.getTime()).toBe(date.getTime())
  })

  it.each(['', '2030-01-05', 'tomorrow', '2030-13-45T99:99'])('rejects %j', (value) => {
    expect(fromDateTimeLocal(value)).toBeNull()
  })
})

describe('defaultDeparture', () => {
  it('rounds up to the next quarter hour after the lead time', () => {
    const result = defaultDeparture(new Date(2030, 0, 5, 7, 2, 30))

    expect(toDateTimeLocal(result)).toBe('2030-01-05T07:30')
  })

  it('keeps an exact quarter hour', () => {
    expect(toDateTimeLocal(defaultDeparture(new Date(2030, 0, 5, 7, 0)))).toBe('2030-01-05T07:15')
  })
})
