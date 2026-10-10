import { z } from 'zod'

/** Mirrors the backend's JSON (backend/trips/api/presenters.py). */

export const RISK_LEVELS = ['low', 'moderate', 'high', 'severe', 'no_travel'] as const
export const riskLevelSchema = z.enum(RISK_LEVELS)
export type RiskLevel = z.infer<typeof riskLevelSchema>

const isoTime = z.iso.datetime()

export const placeSchema = z.object({
  label: z.string(),
  lat: z.number(),
  lon: z.number(),
})
export type Place = z.infer<typeof placeSchema>

export const geocodeResponseSchema = z.object({ results: z.array(placeSchema) })

export const checkpointSchema = z.object({
  mile: z.number(),
  lat: z.number(),
  lon: z.number(),
  eta: isoTime,
  level: riskLevelSchema.nullable(),
  wind_mph: z.number().nullable(),
  gust_mph: z.number().nullable(),
  rain_in_per_hr: z.number().nullable(),
  snow_in_per_hr: z.number().nullable(),
  drivers: z.array(z.enum(['wind', 'rain', 'snow'])),
  load_escalated: z.boolean(),
})
export type Checkpoint = z.infer<typeof checkpointSchema>

export const stopSchema = z.object({
  kind: z.enum(['break', 'rest']),
  mile: z.number(),
  lat: z.number(),
  lon: z.number(),
  starts_at: isoTime,
  ends_at: isoTime,
})
export type Stop = z.infer<typeof stopSchema>

export const routeSchema = z.object({
  id: z.string(),
  rank: z.number().int(),
  recommended: z.boolean(),
  geometry: z.string(),
  distance_mi: z.number(),
  driving_s: z.number(),
  duration_s: z.number(),
  traffic_delay_s: z.number(),
  arrival_time: isoTime,
  risk: z.object({
    miles_by_level: z.record(riskLevelSchema, z.number()),
    unknown_mi: z.number(),
    average: z.number().nullable(),
    worst_level: riskLevelSchema.nullable(),
  }),
  checkpoints: z.array(checkpointSchema),
  stops: z.array(stopSchema),
})
export type Route = z.infer<typeof routeSchema>

export const tripPlanSchema = z.object({
  departure_time: isoTime,
  load_weight_lb: z.number(),
  sample_interval_mi: z.number(),
  hours_of_service: z.boolean(),
  recommendation: z.object({
    route_id: z.string(),
    travel_advised: z.boolean(),
    deciding_factor: z.string(),
    explanation: z.string(),
  }),
  routes: z.array(routeSchema).min(1),
})
export type TripPlan = z.infer<typeof tripPlanSchema>

export interface TripPlanRequest {
  origin: { lat: number; lon: number; label?: string }
  destination: { lat: number; lon: number; label?: string }
  departure_time: string
  load_weight_lb: number
  sample_interval_mi: 10 | 25 | 50
  hours_of_service: boolean
}
