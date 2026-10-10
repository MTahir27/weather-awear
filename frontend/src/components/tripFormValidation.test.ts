import { describe, expect, it } from 'vitest'

import { toDateTimeLocal } from '../lib/format'
import { serverErrorsToForm, validateTripForm, type TripFormValues } from './tripFormValidation'

const NOW = new Date(2030, 0, 5, 7, 0)
const DALLAS = { label: 'Dallas, TX', lat: 32.78, lon: -96.8 }
const HOUSTON = { label: 'Houston, TX', lat: 29.76, lon: -95.37 }

function values(overrides: Partial<TripFormValues> = {}): TripFormValues {
  return {
    origin: DALLAS,
    destination: HOUSTON,
    departure: toDateTimeLocal(new Date(2030, 0, 5, 9, 30)),
    loadWeightLb: '35000',
    intervalMi: 25,
    hoursOfService: true,
    ...overrides,
  }
}

describe('validateTripForm', () => {
  it('builds the API request from valid values', () => {
    const result = validateTripForm(values({ intervalMi: 10, hoursOfService: false }), NOW)

    expect(result).toEqual({
      ok: true,
      request: {
        origin: { lat: 32.78, lon: -96.8, label: 'Dallas, TX' },
        destination: { lat: 29.76, lon: -95.37, label: 'Houston, TX' },
        departure_time: new Date(2030, 0, 5, 9, 30).toISOString(),
        load_weight_lb: 35_000,
        sample_interval_mi: 10,
        hours_of_service: false,
      },
    })
  })

  it.each<[Partial<TripFormValues>, keyof TripFormValues, string]>([
    [{ origin: null }, 'origin', 'Choose an origin'],
    [{ destination: null }, 'destination', 'Choose a destination'],
    [{ destination: { ...DALLAS, label: 'Dallas' } }, 'destination', 'different from the origin'],
    [{ departure: '' }, 'departure', 'Enter a departure'],
    [{ departure: toDateTimeLocal(new Date(2030, 0, 5, 6, 0)) }, 'departure', 'in the past'],
    [{ departure: toDateTimeLocal(new Date(2030, 0, 13, 7, 0)) }, 'departure', 'next 7 days'],
    [{ loadWeightLb: '' }, 'loadWeightLb', 'Enter the load weight'],
    [{ loadWeightLb: '-5' }, 'loadWeightLb', 'positive number'],
    [{ loadWeightLb: 'heavy' }, 'loadWeightLb', 'positive number'],
    [{ loadWeightLb: '150001' }, 'loadWeightLb', 'cannot exceed 150,000 lb'],
  ])('rejects %o', (overrides, field, message) => {
    const result = validateTripForm(values(overrides), NOW)

    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors[field]).toContain(message)
  })

  it('allows a departure a few minutes ago (treated as now by the server)', () => {
    const result = validateTripForm(
      values({ departure: toDateTimeLocal(new Date(2030, 0, 5, 6, 50)) }),
      NOW,
    )

    expect(result.ok).toBe(true)
  })

  it('accepts the boundary loads 0 and 150,000 lb', () => {
    expect(validateTripForm(values({ loadWeightLb: '0' }), NOW).ok).toBe(true)
    expect(validateTripForm(values({ loadWeightLb: '150000' }), NOW).ok).toBe(true)
  })
})

describe('serverErrorsToForm', () => {
  it('maps API field names to form fields and keeps the first message', () => {
    expect(
      serverErrorsToForm({
        departure_time: ['In the past.', 'Second'],
        load_weight_lb: ['Too heavy.'],
        unknown_field: ['Ignored.'],
      }),
    ).toEqual({ departure: 'In the past.', loadWeightLb: 'Too heavy.' })
  })
})
