import type { HeatmapResponse } from '../api/schemas'

export const HEATMAP_METRICS = ['risk', 'wind', 'rain', 'snow'] as const
export type HeatmapMetric = (typeof HEATMAP_METRICS)[number]

export const METRIC_LABEL: Record<HeatmapMetric, string> = {
  risk: 'Overall risk',
  wind: 'Wind',
  rain: 'Rain',
  snow: 'Snow',
}

/**
 * Heatmap frames as typed arrays, ready for the GPU. Every metric is on the
 * same 0-4 risk scale; NaN marks points without forecast data, which are shown
 * as unknown rather than drawn as "low".
 */
export interface HeatmapData {
  departureMs: number
  frameMs: number
  frameCount: number
  positions: [number, number][]
  /** Grid spacing in meters (the corridor grid is regular). */
  cellMeters: number
  frames: Record<HeatmapMetric, Float32Array[]>
}

const METERS_PER_DEGREE_LAT = 111_195

/**
 * The backend places points at cell centres of a regular grid, so the
 * smallest gap between distinct latitudes is one cell.
 */
export function gridCellMeters(latitudes: number[]): number {
  const unique = [...new Set(latitudes.map((lat) => lat.toFixed(4)))]
    .map(Number)
    .sort((a, b) => a - b)
  let smallest = Infinity
  for (let i = 1; i < unique.length; i++) smallest = Math.min(smallest, unique[i]! - unique[i - 1]!)
  // A single row of points: fall back to a typical cell size (~10 km).
  return Number.isFinite(smallest) ? smallest * METERS_PER_DEGREE_LAT : 10_000
}

function toFrames(frames: (number | null)[][], unknown?: number): Float32Array[] {
  return frames.map((frame) =>
    Float32Array.from(frame, (v) => (v === null || v === unknown ? Number.NaN : v)),
  )
}

export function prepareHeatmap(response: HeatmapResponse): HeatmapData {
  return {
    departureMs: Date.parse(response.departure_time),
    frameMs: response.frame_hours * 3600_000,
    frameCount: response.risk.length,
    positions: response.lon.map((lon, i) => [lon, response.lat[i]!]),
    cellMeters: gridCellMeters(response.lat),
    frames: {
      risk: toFrames(response.risk, -1),
      wind: toFrames(response.wind_score),
      rain: toFrames(response.rain_score),
      snow: toFrames(response.snow_score),
    },
  }
}

/**
 * Points worth drawing in a frame: Moderate or worse (score >= 1), plus points
 * without data so gaps in the forecast stay visible. Low points are omitted.
 */
export function visiblePoints(frame: Float32Array): number[] {
  const indices: number[] = []
  frame.forEach((value, i) => {
    if (Number.isNaN(value) || value >= 1) indices.push(i)
  })
  return indices
}
