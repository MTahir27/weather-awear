import { describe, expect, it } from 'vitest'

import { RISK_LEVELS } from '../api/schemas'
import { RISK_STYLE, riskRgb, riskStyle } from './risk'

describe('risk styles', () => {
  it('defines a style for every level the API can return', () => {
    for (const level of RISK_LEVELS) expect(RISK_STYLE[level].label).toBeTruthy()
  })

  it('treats a missing level as Unknown', () => {
    expect(riskStyle(null).label).toBe('Unknown')
  })

  it('converts hex to RGB for deck.gl', () => {
    expect(riskRgb('severe')).toEqual([0xdc, 0x26, 0x26])
    expect(riskRgb(null)).toEqual([0x9c, 0xa3, 0xaf])
  })
})
