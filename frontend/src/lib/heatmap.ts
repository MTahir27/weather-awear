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
 * same 0-4 risk scale; NaN marks points without forecast data, which are left
 * out of the layer instead of being drawn as "low".
 */
export interface HeatmapData {
  departureMs: number
  frameMs: number
  frameCount: number
  positions: [number, number][]
  frames: Record<HeatmapMetric, Float32Array[]>
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
    frames: {
      risk: toFrames(response.risk, -1),
      wind: toFrames(response.wind_score),
      rain: toFrames(response.rain_score),
      snow: toFrames(response.snow_score),
    },
  }
}

/** Indices of points with data in a frame. */
export function knownPoints(frame: Float32Array): Uint32Array {
  const indices: number[] = []
  frame.forEach((value, i) => {
    if (!Number.isNaN(value)) indices.push(i)
  })
  return Uint32Array.from(indices)
}
