import type { Place, TripPlanRequest } from '../api/schemas'
import { fromDateTimeLocal } from '../lib/format'

/** Limits mirror the backend serializer (backend/trips/api/serializers.py). */
export const MAX_LOAD_LB = 150_000
export const SAMPLE_INTERVALS = [10, 25, 50] as const
export type SampleInterval = (typeof SAMPLE_INTERVALS)[number]
const PAST_GRACE_MS = 15 * 60_000
const MAX_AHEAD_MS = 7 * 24 * 3600_000

export interface TripFormValues {
  origin: Place | null
  destination: Place | null
  departure: string
  loadWeightLb: string
  intervalMi: SampleInterval
  hoursOfService: boolean
}

export type TripFormErrors = Partial<Record<keyof TripFormValues, string>>

export type ValidationResult =
  { ok: true; request: TripPlanRequest } | { ok: false; errors: TripFormErrors }

export function validateTripForm(values: TripFormValues, now = new Date()): ValidationResult {
  const errors: TripFormErrors = {}

  if (!values.origin) errors.origin = 'Choose an origin from the suggestions.'
  if (!values.destination) errors.destination = 'Choose a destination from the suggestions.'
  if (
    values.origin &&
    values.destination &&
    values.origin.lat === values.destination.lat &&
    values.origin.lon === values.destination.lon
  ) {
    errors.destination = 'Destination must be different from the origin.'
  }

  const departure = fromDateTimeLocal(values.departure)
  if (!departure) {
    errors.departure = 'Enter a departure date and time.'
  } else if (departure.getTime() < now.getTime() - PAST_GRACE_MS) {
    errors.departure = 'Departure time cannot be in the past.'
  } else if (departure.getTime() > now.getTime() + MAX_AHEAD_MS) {
    errors.departure = 'Departure must be within the next 7 days.'
  }

  const raw = values.loadWeightLb.trim()
  const load = Number(raw)
  if (!raw) {
    errors.loadWeightLb = 'Enter the load weight.'
  } else if (!Number.isFinite(load) || load < 0) {
    errors.loadWeightLb = 'Load weight must be a positive number.'
  } else if (load > MAX_LOAD_LB) {
    errors.loadWeightLb = `Load weight cannot exceed ${MAX_LOAD_LB.toLocaleString('en-US')} lb.`
  }

  if (Object.keys(errors).length || !values.origin || !values.destination || !departure) {
    return { ok: false, errors }
  }
  return {
    ok: true,
    request: {
      origin: { lat: values.origin.lat, lon: values.origin.lon, label: values.origin.label },
      destination: {
        lat: values.destination.lat,
        lon: values.destination.lon,
        label: values.destination.label,
      },
      departure_time: departure.toISOString(),
      load_weight_lb: load,
      sample_interval_mi: values.intervalMi,
      hours_of_service: values.hoursOfService,
    },
  }
}

/** Maps server-side field names onto form fields. */
export function serverErrorsToForm(fieldErrors: Record<string, string[]>): TripFormErrors {
  const fields: Record<string, keyof TripFormValues> = {
    origin: 'origin',
    destination: 'destination',
    departure_time: 'departure',
    load_weight_lb: 'loadWeightLb',
    sample_interval_mi: 'intervalMi',
    hours_of_service: 'hoursOfService',
  }
  const errors: TripFormErrors = {}
  for (const [field, messages] of Object.entries(fieldErrors)) {
    const key = fields[field]
    if (key && messages[0]) errors[key] = messages[0]
  }
  return errors
}
