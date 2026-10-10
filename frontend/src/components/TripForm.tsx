import { useState, type FormEvent } from 'react'

import type { TripPlanRequest } from '../api/schemas'
import { defaultDeparture, toDateTimeLocal } from '../lib/format'
import { PlaceInput } from './PlaceInput'
import {
  MAX_LOAD_LB,
  SAMPLE_INTERVALS,
  validateTripForm,
  type TripFormErrors,
  type TripFormValues,
} from './tripFormValidation'

interface TripFormProps {
  onSubmit: (request: TripPlanRequest) => void
  submitting: boolean
  serverErrors?: TripFormErrors
}

const fieldClass =
  'w-full rounded-lg border bg-white px-3 py-2 text-sm shadow-sm outline-none focus:ring-2 focus:ring-sky-500'

export function TripForm({ onSubmit, submitting, serverErrors = {} }: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>(() => ({
    origin: null,
    destination: null,
    departure: toDateTimeLocal(defaultDeparture()),
    loadWeightLb: '',
    intervalMi: 25,
    hoursOfService: true,
  }))
  // Picker hints only; validateTripForm enforces the real window at submit time.
  const [pickerBounds] = useState(() => {
    const now = Date.now()
    return {
      min: toDateTimeLocal(new Date(now)),
      max: toDateTimeLocal(new Date(now + 7 * 24 * 3600_000)),
    }
  })
  const [errors, setErrors] = useState<TripFormErrors>({})
  const shown = { ...serverErrors, ...errors }

  const update = <K extends keyof TripFormValues>(key: K, value: TripFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: undefined }))
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const result = validateTripForm(values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    onSubmit(result.request)
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4" aria-label="Plan a trip">
      <PlaceInput
        label="Origin"
        placeholder="City, address or place"
        value={values.origin}
        onChange={(place) => update('origin', place)}
        error={shown.origin}
      />
      <PlaceInput
        label="Destination"
        placeholder="City, address or place"
        value={values.destination}
        onChange={(place) => update('destination', place)}
        error={shown.destination}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="departure" className="mb-1 block text-sm font-medium text-slate-700">
            Departure
          </label>
          <input
            id="departure"
            type="datetime-local"
            value={values.departure}
            min={pickerBounds.min}
            max={pickerBounds.max}
            onChange={(event) => update('departure', event.target.value)}
            aria-invalid={Boolean(shown.departure)}
            aria-describedby={shown.departure ? 'departure-error' : undefined}
            className={`${fieldClass} ${shown.departure ? 'border-red-500' : 'border-slate-300'}`}
          />
          {shown.departure && (
            <p id="departure-error" className="mt-1 text-xs text-red-600">
              {shown.departure}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="load" className="mb-1 block text-sm font-medium text-slate-700">
            Load weight (lb)
          </label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_LOAD_LB}
            step={100}
            placeholder="e.g. 35000"
            value={values.loadWeightLb}
            onChange={(event) => update('loadWeightLb', event.target.value)}
            aria-invalid={Boolean(shown.loadWeightLb)}
            aria-describedby={shown.loadWeightLb ? 'load-error' : undefined}
            className={`${fieldClass} ${shown.loadWeightLb ? 'border-red-500' : 'border-slate-300'}`}
          />
          {shown.loadWeightLb && (
            <p id="load-error" className="mt-1 text-xs text-red-600">
              {shown.loadWeightLb}
            </p>
          )}
        </div>
      </div>

      <fieldset>
        <legend className="mb-1 block text-sm font-medium text-slate-700">
          Check weather every
        </legend>
        <div className="grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1">
          {SAMPLE_INTERVALS.map((interval) => (
            <label
              key={interval}
              className={`cursor-pointer rounded-md py-1.5 text-center text-sm font-medium has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sky-500 ${
                values.intervalMi === interval
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <input
                type="radio"
                name="interval"
                value={interval}
                checked={values.intervalMi === interval}
                onChange={() => update('intervalMi', interval)}
                className="sr-only"
              />
              {interval} mi
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex items-start gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={values.hoursOfService}
          onChange={(event) => update('hoursOfService', event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
        />
        <span>
          Include driver rest stops
          <span className="block text-xs text-slate-500">
            30-min break after 8 h driving, 10 h off after 11 h (FMCSA)
          </span>
        </span>
      </label>

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:outline-none disabled:cursor-wait disabled:opacity-70"
      >
        {submitting ? 'Checking routes and weather…' : 'Find the safest route'}
      </button>
    </form>
  )
}
