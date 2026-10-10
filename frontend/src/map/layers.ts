import type { Layer, PickingInfo } from '@deck.gl/core'
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'

import type { Checkpoint, Route, Stop, TripPlan } from '../api/schemas'
import { formatDuration, formatTime } from '../lib/format'
import { pointAtMile, riskStretches, type LonLat, type RiskStretch } from '../lib/geometry'
import { visiblePoints, type HeatmapData, type HeatmapMetric } from '../lib/heatmap'
import { decodePolyline } from '../lib/polyline'
import { FACTOR_LABEL, riskRgb, riskStyle } from '../lib/risk'
import { routeName } from '../lib/routes'
import { truckProgressAt, type TruckStatus } from '../lib/truck'

export interface MapRoute {
  route: Route
  name: string
  path: LonLat[]
  stretches: RiskStretch[]
}

type Rgba = [number, number, number, number]
const ALTERNATIVE: Rgba = [71, 85, 105, 150]
const CASING: Rgba = [255, 255, 255, 255]
const STOP_FILL: Rgba = [15, 23, 42, 255]

/** Decodes geometry and risk stretches once per plan. */
export function prepareRoutes(plan: TripPlan): MapRoute[] {
  return plan.routes.map((route) => {
    const path = decodePolyline(route.geometry)
    return {
      route,
      name: routeName(route.rank),
      path,
      stretches: riskStretches(path, route.checkpoints, route.distance_mi),
    }
  })
}

interface LayerOptions {
  routes: MapRoute[]
  selectedId: string
  onSelectRoute: (routeId: string) => void
}

/** deck.gl layers, bottom to top: alternatives, selected route by risk, stops, checkpoints. */
export function buildLayers({ routes, selectedId, onSelectRoute }: LayerOptions): Layer[] {
  const selected = routes.find((r) => r.route.id === selectedId)
  const alternatives = routes.filter((r) => r.route.id !== selectedId)

  const layers: Layer[] = [
    new PathLayer<MapRoute>({
      id: 'alternative-routes',
      data: alternatives,
      getPath: (d) => d.path,
      getColor: ALTERNATIVE,
      getWidth: 5,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      pickable: true,
      autoHighlight: true,
      highlightColor: [14, 165, 233, 200],
      onClick: ({ object }) => {
        if (object) onSelectRoute(object.route.id)
      },
    }),
  ]
  if (!selected) return layers

  layers.push(
    new PathLayer<MapRoute>({
      id: 'selected-route-casing',
      data: [selected],
      getPath: (d) => d.path,
      getColor: CASING,
      getWidth: 10,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
    }),
    new PathLayer<RiskStretch>({
      id: 'selected-route-risk',
      data: selected.stretches,
      getPath: (d) => d.path,
      getColor: (d) => riskRgb(d.level),
      getWidth: 6,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
    }),
    new ScatterplotLayer<Stop>({
      id: 'rest-stops',
      data: selected.route.stops,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: STOP_FILL,
      getLineColor: CASING,
      getRadius: (d) => (d.kind === 'rest' ? 8 : 6),
      radiusUnits: 'pixels',
      lineWidthUnits: 'pixels',
      getLineWidth: 2,
      stroked: true,
      pickable: true,
    }),
    new ScatterplotLayer<Checkpoint>({
      id: 'checkpoints',
      data: selected.route.checkpoints,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => riskRgb(d.level),
      getLineColor: CASING,
      getRadius: 5,
      radiusUnits: 'pixels',
      lineWidthUnits: 'pixels',
      getLineWidth: 1.5,
      stroked: true,
      pickable: true,
    }),
  )
  return layers
}

const escape = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

function value(amount: number | null, unit: string, digits = 0): string {
  return amount === null ? 'n/a' : `${amount.toFixed(digits)} ${unit}`
}

type Rgba4 = [number, number, number, number]
const HEAT_ALPHA = 150
const UNKNOWN_HEAT: Rgba4 = [...riskRgb(null), 90]
const BAND_LEVELS = ['moderate', 'high', 'severe', 'no_travel'] as const
const BAND_COLORS: Rgba4[] = BAND_LEVELS.map((level) => [...riskRgb(level), HEAT_ALPHA])

/** Colour for a 0-4 score: its risk band, exactly as the legend shows it. */
export function heatColor(score: number): Rgba4 {
  if (Number.isNaN(score)) return UNKNOWN_HEAT
  return BAND_COLORS[Math.min(Math.floor(score), 4) - 1] ?? [0, 0, 0, 0]
}

/**
 * Weather heatmap: one translucent disc per corridor grid cell, sized in
 * meters to cover the cell so neighbours merge into a continuous surface.
 *
 * Kernel-density heatmaps were rejected: their smoothing averages an isolated
 * hazardous cell with calm neighbours until it disappears, hiding exactly the
 * conditions a driver needs to see. Each cell here shows its own band.
 */
export function buildHeatmapLayer(
  data: HeatmapData,
  metric: HeatmapMetric,
  frameIndex: number,
): Layer {
  const frame = data.frames[metric][frameIndex] ?? new Float32Array()
  return new ScatterplotLayer<number>({
    id: 'weather-heatmap',
    data: visiblePoints(frame),
    getPosition: (i) => data.positions[i]!,
    getFillColor: (i) => heatColor(frame[i]!),
    // Covers the cell's corners (half-diagonal is ~0.71 of the spacing).
    getRadius: data.cellMeters * 0.75,
    radiusUnits: 'meters',
    stroked: false,
    updateTriggers: { getFillColor: [metric, frameIndex] },
  })
}

export interface TruckMarker {
  name: string
  selected: boolean
  position: LonLat
  status: TruckStatus
  mile: number
}

export function truckMarkers(
  routes: MapRoute[],
  selectedId: string,
  departureMs: number,
  atMs: number,
): TruckMarker[] {
  return routes.map((r) => {
    const progress = truckProgressAt(r.route, departureMs, atMs)
    return {
      name: r.name,
      selected: r.route.id === selectedId,
      position: pointAtMile(r.path, r.route.distance_mi, progress.mile),
      status: progress.status,
      mile: progress.mile,
    }
  })
}

export function buildTruckLayer(trucks: TruckMarker[]): Layer {
  return new ScatterplotLayer<TruckMarker>({
    id: 'trucks',
    // Draw the selected route's truck last so it sits on top.
    data: [...trucks].sort((a, b) => Number(a.selected) - Number(b.selected)),
    getPosition: (d) => d.position,
    getFillColor: (d) => (d.selected ? [2, 132, 199, 255] : [100, 116, 139, 220]),
    getLineColor: [255, 255, 255, 255],
    getRadius: (d) => (d.selected ? 10 : 7),
    radiusUnits: 'pixels',
    lineWidthUnits: 'pixels',
    getLineWidth: 3,
    stroked: true,
    pickable: true,
  })
}

const STATUS_LABEL: Record<TruckStatus, string> = {
  waiting: 'Not departed yet',
  driving: 'Driving',
  resting: 'Resting',
  arrived: 'Arrived',
}

export function truckTooltip(t: TruckMarker): string {
  return `<div class="font-semibold">${escape(t.name)} truck</div><div>${STATUS_LABEL[t.status]} · mile ${Math.round(t.mile)}</div>`
}

export function checkpointTooltip(c: Checkpoint): string {
  const style = riskStyle(c.level)
  const cause = c.drivers.length
    ? ` · ${c.drivers.map((d) => FACTOR_LABEL[d]).join(' + ')}${c.load_escalated ? ' + heavy load' : ''}`
    : ''
  const gusty = c.gust_mph !== null && c.gust_mph >= 45 ? ' ⚠ gusty' : ''
  return `
    <div class="font-semibold">Mile ${Math.round(c.mile)} · ${escape(formatTime(c.eta))}</div>
    <div>Risk: <b>${style.label}</b>${escape(cause)}</div>
    <div>Wind ${value(c.wind_mph, 'mph')} (gusts ${value(c.gust_mph, 'mph')})${gusty}</div>
    <div>Rain ${value(c.rain_in_per_hr, 'in/hr', 2)} · Snow ${value(c.snow_in_per_hr, 'in/hr', 2)}</div>`
}

export function stopTooltip(s: Stop): string {
  const minutes = (Date.parse(s.ends_at) - Date.parse(s.starts_at)) / 1000
  const kind = s.kind === 'rest' ? 'Rest stop' : 'Break'
  return `
    <div class="font-semibold">${kind} · ${formatDuration(minutes)}</div>
    <div>Mile ${Math.round(s.mile)}</div>
    <div>${escape(formatTime(s.starts_at))} → ${escape(formatTime(s.ends_at))}</div>`
}

export function tooltipFor(info: PickingInfo): { html: string; className: string } | null {
  const { object, layer } = info
  if (!object || !layer) return null
  let html: string | null = null
  if (layer.id === 'checkpoints') html = checkpointTooltip(object as Checkpoint)
  else if (layer.id === 'rest-stops') html = stopTooltip(object as Stop)
  else if (layer.id === 'trucks') html = truckTooltip(object as TruckMarker)
  else if (layer.id === 'alternative-routes')
    html = `<div class="font-semibold">${escape((object as MapRoute).name)}</div><div>Click to select</div>`
  return html ? { html, className: 'map-tooltip' } : null
}
