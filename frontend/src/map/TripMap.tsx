import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import { setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useMemo, useRef } from 'react'
import Map, {
  AttributionControl,
  NavigationControl,
  useControl,
  type MapRef,
} from 'react-map-gl/maplibre'

import type { TripPlan } from '../api/schemas'
import type { MetricChoice } from '../components/TimeControls'
import { boundsOf } from '../lib/geometry'
import type { HeatmapData } from '../lib/heatmap'
import { RiskLegend } from './RiskLegend'
import { RouteLabels } from './RouteLabels'
import {
  buildHeatmapLayer,
  buildLayers,
  buildTruckLayer,
  prepareRoutes,
  tooltipFor,
  truckMarkers,
} from './layers'

// MapLibre builds its worker URL at runtime, which bundlers cannot detect, so
// the worker is never emitted and tiles silently fail to load. Emit it explicitly.
setWorkerUrl(maplibreWorkerUrl)

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron'
const CONTINENTAL_US = { longitude: -98.5, latitude: 39.5, zoom: 3.3 }

function DeckOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props))
  overlay.setProps(props)
  return null
}

interface TripMapProps {
  plan: TripPlan | null
  selectedId: string
  onSelectRoute: (routeId: string) => void
  heatmap: HeatmapData | null
  metric: MetricChoice
  frame: number
}

export default function TripMap({
  plan,
  selectedId,
  onSelectRoute,
  heatmap,
  metric,
  frame,
}: TripMapProps) {
  const mapRef = useRef<MapRef>(null)
  const routes = useMemo(() => (plan ? prepareRoutes(plan) : []), [plan])
  // Route layers do not depend on the forecast hour, so scrubbing the slider
  // only rebuilds the heatmap and truck layers.
  const routeLayers = useMemo(
    () => buildLayers({ routes, selectedId, onSelectRoute }),
    [routes, selectedId, onSelectRoute],
  )
  const heatmapLayer = useMemo(
    () => (heatmap && metric !== 'off' ? buildHeatmapLayer(heatmap, metric, frame) : null),
    [heatmap, metric, frame],
  )
  const truckLayer = useMemo(() => {
    if (!plan || routes.length === 0) return null
    const departureMs = Date.parse(plan.departure_time)
    const atMs = departureMs + frame * 3600_000
    return buildTruckLayer(truckMarkers(routes, selectedId, departureMs, atMs))
  }, [plan, routes, selectedId, frame])
  const layers = useMemo(
    () => [heatmapLayer, ...routeLayers, truckLayer].filter((l) => l !== null),
    [heatmapLayer, routeLayers, truckLayer],
  )

  useEffect(() => {
    const bounds = boundsOf(routes.map((r) => r.path))
    if (bounds) mapRef.current?.fitBounds(bounds, { padding: 60, duration: 800 })
  }, [routes])

  return (
    <div className="relative h-full w-full">
      <Map
        ref={mapRef}
        initialViewState={CONTINENTAL_US}
        mapStyle={MAP_STYLE}
        style={{ width: '100%', height: '100%' }}
        dragRotate={false}
        touchPitch={false}
        attributionControl={false}
      >
        <NavigationControl position="top-right" showCompass={false} />
        {/* Top-right keeps the required attribution clear of the time controls. */}
        <AttributionControl position="top-right" compact />
        <DeckOverlay layers={layers} getTooltip={tooltipFor} />
        <RouteLabels routes={routes} selectedId={selectedId} onSelectRoute={onSelectRoute} />
      </Map>
      {plan && <RiskLegend />}
    </div>
  )
}
