import { describe, expect, it } from 'vitest'

import { decodePolyline } from './polyline'

describe('decodePolyline', () => {
  it("decodes Google's reference example (same string the backend test encodes)", () => {
    expect(decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')).toEqual([
      [-120.2, 38.5],
      [-120.95, 40.7],
      [-126.453, 43.252],
    ])
  })

  it('returns no points for an empty string', () => {
    expect(decodePolyline('')).toEqual([])
  })

  it('rejects truncated input', () => {
    expect(() => decodePolyline('_p~iF~ps|')).toThrow('Malformed polyline')
  })
})
