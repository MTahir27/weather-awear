import type { PickingInfo } from '@deck.gl/core'
import { describe, expect, it, vi } from 'vitest'

import { tripPlanSchema, type Checkpoint, type Stop } from '../api/schemas'
import tripPlanFixture from '../test/fixtures/trip-plan.json'
import { buildLayers, checkpointTooltip, prepareRoutes, stopTooltip, tooltipFor } from './layers'

const PLAN = tripPlanSchema.parse(tripPlanFixture)

const CHECKPOINT: Checkpoint = {
  mile: 125.4,
  lat: 40,
  lon: -100,
  eta: '2030-01-01T15:17:00Z',
  level: 'no_travel',
  wind_mph: 47.2,
  gust_mph: 61,
  rain_in_per_hr: 0.02,
  snow_in_per_hr: null,
  drivers: ['wind'],
  load_escalated: true,
}

describe('prepareRoutes', () => {
  it('decodes every route and splits it into risk stretches', () => {
    const routes = prepareRoutes(PLAN)

    expect(routes.map((r) => r.name)).toEqual(['Route A', 'Route B', 'Route C'])
    for (const r of routes) {
      expect(r.path.length).toBeGreaterThan(10)
      expect(r.stretches.length).toBeGreaterThan(0)
      // Decoded geometry lies around Texas.
      expect(r.path[0]![0]).toBeCloseTo(-96.8, 0)
    }
  })
})

describe('buildLayers', () => {
  it('draws alternatives below the selected route, then stops and checkpoints', () => {
    const routes = prepareRoutes(PLAN)

    const layers = buildLayers({ routes, selectedId: 'route-2', onSelectRoute: vi.fn() })

    expect(layers.map((l) => l.id)).toEqual([
      'alternative-routes',
      'selected-route-casing',
      'selected-route-risk',
      'rest-stops',
      'checkpoints',
    ])
    expect((layers[0]!.props.data as unknown[]).length).toBe(2)
    expect(layers[4]!.props.data).toBe(PLAN.routes[1]!.checkpoints)
  })

  it('selects an alternative route when it is clicked', () => {
    const onSelectRoute = vi.fn()
    const routes = prepareRoutes(PLAN)
    const [alternatives] = buildLayers({ routes, selectedId: 'route-1', onSelectRoute })

    alternatives!.props.onClick?.({ object: routes[2] } as PickingInfo, {} as never)

    expect(onSelectRoute).toHaveBeenCalledWith(routes[2]!.route.id)
  })

  it('draws only alternatives when nothing is selected', () => {
    const layers = buildLayers({
      routes: prepareRoutes(PLAN),
      selectedId: '',
      onSelectRoute: vi.fn(),
    })

    expect(layers.map((l) => l.id)).toEqual(['alternative-routes'])
  })
})

describe('tooltips', () => {
  it('explains a checkpoint, including load escalation, gusts and missing data', () => {
    const html = checkpointTooltip(CHECKPOINT)

    expect(html).toContain('Mile 125')
    expect(html).toContain('<b>No Travel</b>')
    expect(html).toContain('Wind + heavy load')
    expect(html).toContain('Wind 47 mph (gusts 61 mph) ⚠ gusty')
    expect(html).toContain('Snow n/a')
  })

  it('describes rest stops with their duration', () => {
    const stop: Stop = {
      kind: 'rest',
      mile: 550,
      lat: 40,
      lon: -100,
      starts_at: '2030-01-01T19:30:00Z',
      ends_at: '2030-01-02T05:30:00Z',
    }

    expect(stopTooltip(stop)).toContain('Rest stop · 10 h')
  })

  it('routes picking info to the right tooltip', () => {
    const routes = prepareRoutes(PLAN)
    const info = (layerId: string, object: unknown) =>
      ({ object, layer: { id: layerId } }) as unknown as PickingInfo

    expect(tooltipFor(info('checkpoints', CHECKPOINT))?.html).toContain('Mile 125')
    expect(tooltipFor(info('alternative-routes', routes[1]))?.html).toContain('Route B')
    expect(tooltipFor(info('selected-route-risk', {}))).toBeNull()
    expect(tooltipFor(info('checkpoints', null))).toBeNull()
  })
})
