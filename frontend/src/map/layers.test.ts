import type { PickingInfo } from '@deck.gl/core'
import { describe, expect, it, vi } from 'vitest'

import { tripPlanSchema, type Checkpoint, type Stop } from '../api/schemas'
import tripPlanFixture from '../test/fixtures/trip-plan.json'
import { prepareHeatmap } from '../lib/heatmap'
import {
  buildHeatmapLayer,
  buildLayers,
  buildTruckLayer,
  checkpointTooltip,
  heatColor,
  prepareRoutes,
  stopTooltip,
  tooltipFor,
  truckMarkers,
  truckTooltip,
} from './layers'

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

describe('heatmap and truck layers', () => {
  const heatmap = prepareHeatmap({
    departure_time: PLAN.departure_time,
    frame_hours: 1,
    lat: [32, 31, 30],
    lon: [-96, -96, -96],
    risk: [
      [0, 2, -1],
      [4, 4, 4],
    ],
    wind_score: [
      [0.5, 1.5, null],
      [3, 3, 3],
    ],
    rain_score: [
      [0, 0, 0],
      [0, 0, 0],
    ],
    snow_score: [
      [0, 0, 0],
      [0, 0, 0],
    ],
  })

  it('draws Moderate-or-worse and unknown cells, sized to the grid', () => {
    const layer = buildHeatmapLayer(heatmap, 'risk', 0)

    expect(layer.id).toBe('weather-heatmap')
    // Point 0 is Low (omitted), 1 is High, 2 has no data.
    expect(layer.props.data).toEqual([1, 2])
    expect(layer.props).toMatchObject({ radiusUnits: 'meters' })
    expect(heatmap.cellMeters).toBeCloseTo(111_195)
  })

  it('colours cells by the band of the requested metric and frame', () => {
    const layer = buildHeatmapLayer(heatmap, 'wind', 1)
    const { getFillColor } = layer.props as unknown as { getFillColor: (i: number) => number[] }

    expect(getFillColor(2).slice(0, 3)).toEqual([0xdc, 0x26, 0x26]) // score 3 -> Severe
  })

  it.each([
    [0.99, 0],
    [1, 0xea],
    [2.5, 0xf9],
    [3.999, 0xdc],
    [4, 0x7e],
  ])('maps score %s to its band colour', (score, red) => {
    const color = heatColor(score)
    expect(red === 0 ? color[3] : color[0]).toBe(red)
  })

  it('shows missing data as translucent grey', () => {
    expect(heatColor(Number.NaN)).toEqual([0x9c, 0xa3, 0xaf, 90])
  })

  it('places a truck on every route, selected one drawn last', () => {
    const routes = prepareRoutes(PLAN)
    const departure = Date.parse(PLAN.departure_time)
    const trucks = truckMarkers(routes, 'route-1', departure, departure + 3600_000)

    expect(trucks).toHaveLength(3)
    expect(trucks.every((t) => t.status === 'driving' && t.mile > 0)).toBe(true)
    const layer = buildTruckLayer(trucks)
    const drawn = layer.props.data as typeof trucks
    expect(drawn.at(-1)!.selected).toBe(true)
    expect(truckTooltip(trucks[0]!)).toContain('Route A truck')
    expect(
      tooltipFor({ object: trucks[0], layer: { id: 'trucks' } } as unknown as PickingInfo)?.html,
    ).toContain('Driving')
  })
})
