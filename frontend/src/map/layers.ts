import type { Layer, PickingInfo } from '@deck.gl/core'
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers'

import type { Checkpoint, Route, Stop, TripPlan } from '../api/schemas'
import { formatDuration, formatTime } from '../lib/format'
import { riskStretches, type LonLat, type RiskStretch } from '../lib/geometry'
import { decodePolyline } from '../lib/polyline'
import { FACTOR_LABEL, riskRgb, riskStyle } from '../lib/risk'
import { routeName } from '../lib/routes'

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
  else if (layer.id === 'alternative-routes')
    html = `<div class="font-semibold">${escape((object as MapRoute).name)}</div><div>Click to select</div>`
  return html ? { html, className: 'map-tooltip' } : null
}
