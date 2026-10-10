import type { z } from 'zod'

import {
  geocodeResponseSchema,
  heatmapSchema,
  tripPlanSchema,
  type HeatmapRequest,
  type HeatmapResponse,
  type Place,
  type TripPlan,
  type TripPlanRequest,
} from './schemas'

export class ApiError extends Error {
  readonly status: number
  /** Field-level validation messages from the server, keyed by field name. */
  readonly fieldErrors: Record<string, string[]>

  constructor(status: number, message: string, fieldErrors: Record<string, string[]> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

function errorFromBody(status: number, body: unknown): ApiError {
  if (body && typeof body === 'object') {
    if ('detail' in body && typeof body.detail === 'string') {
      return new ApiError(status, body.detail)
    }
    // DRF validation errors: { field: ["message", ...] } (possibly nested one level).
    const fieldErrors: Record<string, string[]> = {}
    for (const [field, value] of Object.entries(body)) {
      const messages = Array.isArray(value)
        ? value.filter((m): m is string => typeof m === 'string')
        : value && typeof value === 'object'
          ? Object.values(value)
              .flat()
              .filter((m): m is string => typeof m === 'string')
          : []
      if (messages.length) fieldErrors[field] = messages
    }
    if (Object.keys(fieldErrors).length) {
      return new ApiError(status, 'Please correct the highlighted fields.', fieldErrors)
    }
  }
  if (status === 429) return new ApiError(status, 'Too many requests. Please wait a moment.')
  return new ApiError(status, `Request failed with status ${status}`)
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.')
  }
  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) throw errorFromBody(response.status, body)

  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    throw new ApiError(response.status, 'The server returned an unexpected response.')
  }
  return parsed.data
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const params = new URLSearchParams({ q: query })
  const data = await request(`/geocode?${params}`, geocodeResponseSchema, { signal })
  return data.results
}

export function planTrip(body: TripPlanRequest, signal?: AbortSignal): Promise<TripPlan> {
  return request('/trips/plan', tripPlanSchema, {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
  })
}

export function fetchHeatmap(body: HeatmapRequest, signal?: AbortSignal): Promise<HeatmapResponse> {
  return request('/trips/heatmap', heatmapSchema, {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
  })
}
