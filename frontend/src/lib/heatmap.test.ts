import { describe, expect, it } from 'vitest'

import { heatmapSchema, type HeatmapResponse } from '../api/schemas'
import { knownPoints, prepareHeatmap } from './heatmap'

const RESPONSE: HeatmapResponse = {
  departure_time: '2030-01-01T08:00:00Z',
  frame_hours: 1,
  lat: [40, 41],
  lon: [-100, -99],
  risk: [
    [0, -1],
    [3, 4],
  ],
  wind_score: [
    [0.2, null],
    [2.5, 4],
  ],
  rain_score: [
    [0, 0],
    [1.5, 0],
  ],
  snow_score: [
    [0, 0],
    [0, 3.2],
  ],
}

describe('heatmapSchema', () => {
  it('accepts consistent frames', () => {
    expect(heatmapSchema.safeParse(RESPONSE).success).toBe(true)
  })

  it('rejects frames whose size does not match the points', () => {
    const broken = { ...RESPONSE, wind_score: [[0.2], [2.5, 4]] }

    expect(heatmapSchema.safeParse(broken).success).toBe(false)
  })

  it('rejects risk levels outside -1..4', () => {
    expect(
      heatmapSchema.safeParse({
        ...RESPONSE,
        risk: [
          [5, 0],
          [0, 0],
        ],
      }).success,
    ).toBe(false)
  })
})

describe('prepareHeatmap', () => {
  it('builds positions and typed frames, with unknowns as NaN', () => {
    const data = prepareHeatmap(RESPONSE)

    expect(data.departureMs).toBe(Date.UTC(2030, 0, 1, 8))
    expect(data.frameMs).toBe(3600_000)
    expect(data.frameCount).toBe(2)
    expect(data.positions).toEqual([
      [-100, 40],
      [-99, 41],
    ])
    expect(Array.from(data.frames.risk[0]!)).toEqual([0, Number.NaN])
    expect(Array.from(data.frames.wind[0]!)).toEqual([expect.closeTo(0.2), Number.NaN])
    expect(data.frames.snow[1]![1]).toBeCloseTo(3.2)
  })

  it('lists only points with data', () => {
    const data = prepareHeatmap(RESPONSE)

    expect(Array.from(knownPoints(data.frames.risk[0]!))).toEqual([0])
    expect(Array.from(knownPoints(data.frames.risk[1]!))).toEqual([0, 1])
  })
})
