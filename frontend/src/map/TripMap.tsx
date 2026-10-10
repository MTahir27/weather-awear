import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef } from 'react'
import Map, { NavigationControl, useControl, type MapRef } from 'react-map-gl/maplibre'

import type { TripPlan } from '../api/schemas'
import { boundsOf } from '../lib/geometry'
import { RiskLegend } from './RiskLegend'
import { buildLayers, prepareRoutes, tooltipFor } from './layers'

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
}

export default function TripMap({ plan, selectedId, onSelectRoute }: TripMapProps) {
  const mapRef = useRef<MapRef>(null)
  const routes = useMemo(() => (plan ? prepareRoutes(plan) : []), [plan])
  const layers = useMemo(
    () => buildLayers({ routes, selectedId, onSelectRoute }),
    [routes, selectedId, onSelectRoute],
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
      >
        <NavigationControl position="top-right" showCompass={false} />
        <DeckOverlay layers={layers} getTooltip={tooltipFor} />
      </Map>
      {plan && <RiskLegend />}
    </div>
  )
}
