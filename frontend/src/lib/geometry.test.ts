import { describe, expect, it } from 'vitest'

import { boundsOf, haversineMiles, riskStretches, type LonLat } from './geometry'

// Due north along a meridian: 1 degree of latitude is ~69.09 miles.
const MILES_PER_DEGREE = 69.09
const NORTH: LonLat[] = Array.from({ length: 11 }, (_, i) => [-100, 40 + i / 10])
const TOTAL = haversineMiles(NORTH[0]!, NORTH[10]!)

describe('haversineMiles', () => {
  it('measures a degree of latitude', () => {
    expect(haversineMiles([0, 0], [0, 1])).toBeCloseTo(MILES_PER_DEGREE, 1)
  })
})

describe('riskStretches', () => {
  it('splits at the midpoints between checkpoints', () => {
    const stretches = riskStretches(
      NORTH,
      [
        { mile: 0, level: 'low' },
        { mile: TOTAL / 2, level: 'severe' },
        { mile: TOTAL, level: 'low' },
      ],
      TOTAL,
    )

    expect(stretches.map((s) => s.level)).toEqual(['low', 'severe', 'low'])
    // Boundaries at 1/4 and 3/4 of the way: latitudes 40.25 and 40.75.
    expect(stretches[0]!.path.at(-1)![1]).toBeCloseTo(40.25, 6)
    expect(stretches[1]!.path[0]![1]).toBeCloseTo(40.25, 6)
    expect(stretches[1]!.path.at(-1)![1]).toBeCloseTo(40.75, 6)
    expect(stretches[2]!.path.at(-1)).toEqual(NORTH[10])
  })

  it('merges adjacent checkpoints with the same level', () => {
    const stretches = riskStretches(
      NORTH,
      [0, 0.25, 0.5, 0.75, 1].map((f, i) => ({
        mile: TOTAL * f,
        level: i < 3 ? ('low' as const) : ('high' as const),
      })),
      TOTAL,
    )

    expect(stretches.map((s) => s.level)).toEqual(['low', 'high'])
  })

  it('covers the whole path without gaps', () => {
    const stretches = riskStretches(
      NORTH,
      [
        { mile: 0, level: 'low' },
        { mile: TOTAL * 0.33, level: null },
        { mile: TOTAL, level: 'moderate' },
      ],
      TOTAL,
    )

    expect(stretches[0]!.path[0]).toEqual(NORTH[0])
    for (let i = 1; i < stretches.length; i++) {
      expect(stretches[i]!.path[0]).toEqual(stretches[i - 1]!.path.at(-1))
    }
    expect(stretches.at(-1)!.path.at(-1)).toEqual(NORTH[10])
  })

  it('scales the measured path to the reported route length', () => {
    // Reported length is double the geometric length: midpoint mile is still mid-path.
    const stretches = riskStretches(
      NORTH,
      [
        { mile: 0, level: 'low' },
        { mile: TOTAL * 2, level: 'high' },
      ],
      TOTAL * 2,
    )

    expect(stretches[0]!.path.at(-1)![1]).toBeCloseTo(40.5, 6)
  })

  it('returns nothing for degenerate input', () => {
    expect(riskStretches([[0, 0]], [{ mile: 0, level: 'low' }], 0)).toEqual([])
    expect(riskStretches(NORTH, [], TOTAL)).toEqual([])
  })
})

describe('boundsOf', () => {
  it('covers every path', () => {
    expect(
      boundsOf([
        [
          [-100, 40],
          [-95, 42],
        ],
        [[-101, 39]],
      ]),
    ).toEqual([
      [-101, 39],
      [-95, 42],
    ])
  })

  it('is null without points', () => {
    expect(boundsOf([])).toBeNull()
  })
})
