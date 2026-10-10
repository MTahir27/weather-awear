import { describe, expect, it } from 'vitest'

import { etaLabelCheckpoints, labelFraction, riskBreakdown, riskSummary } from './routes'

const risk = (miles: Partial<Record<string, number>>, unknown = 0) => ({
  miles_by_level: { low: 100, moderate: 0, high: 0, severe: 0, no_travel: 0, ...miles },
  unknown_mi: unknown,
  average: 0,
  worst_level: 'low' as const,
})

describe('riskSummary', () => {
  it.each([
    [risk({}), 'All Low'],
    [risk({ moderate: 30.4 }), 'Moderate 30 mi'],
    [risk({ moderate: 30, high: 5 }), 'High 5 mi'],
    [risk({ high: 25.4 }), 'High 25 mi'],
    [risk({ no_travel: 3, severe: 12, high: 0.2 }), 'No Travel 3 mi · Severe 12 mi'],
    [risk({}, 40), 'Unknown 40 mi'],
  ])('%o -> %s', (input, expected) => {
    expect(riskSummary(input)).toBe(expected)
  })
})

describe('labelFraction', () => {
  it('staggers labels by rank so routes sharing ends do not collide', () => {
    expect([1, 2, 3, 4].map(labelFraction)).toEqual([0.5, 0.3, 0.7, 0.5])
  })
})

describe('etaLabelCheckpoints', () => {
  const every25 = (to: number) =>
    Array.from({ length: Math.floor(to / 25) + 1 }, (_, i) => ({ mile: i * 25 })).concat(
      to % 25 ? [{ mile: to }] : [],
    )

  it('labels the start, about every 100 miles and the destination', () => {
    expect(etaLabelCheckpoints(every25(420)).map((c) => c.mile)).toEqual([0, 100, 200, 300, 420])
  })

  it('drops a label that would crowd the destination', () => {
    expect(etaLabelCheckpoints(every25(320)).map((c) => c.mile)).toEqual([0, 100, 200, 320])
  })

  it('handles sparse checkpoints and short trips', () => {
    expect(
      etaLabelCheckpoints([{ mile: 0 }, { mile: 150 }, { mile: 260 }]).map((c) => c.mile),
    ).toEqual([0, 150, 260])
    expect(etaLabelCheckpoints([{ mile: 0 }, { mile: 40 }]).map((c) => c.mile)).toEqual([0, 40])
    expect(etaLabelCheckpoints([])).toEqual([])
  })
})

describe('riskBreakdown', () => {
  it('is empty when the whole route is Low', () => {
    expect(riskBreakdown(risk({}))).toEqual([])
  })

  it('lists only the levels the route reaches, worst first, including Moderate', () => {
    expect(
      riskBreakdown(risk({ moderate: 30, no_travel: 50 }, 2)).map((i) => [i.label, i.miles]),
    ).toEqual([
      ['No Travel', 50],
      ['Moderate', 30],
      ['Unknown', 2],
    ])
  })

  it('ignores distances that would display as 0 mi', () => {
    expect(riskBreakdown(risk({ high: 0.01 }))).toEqual([])
  })
})
