/** Decodes Google encoded polylines (precision 5) into [lon, lat] pairs for deck.gl. */
export function decodePolyline(encoded: string, precision = 5): [number, number][] {
  const factor = 10 ** precision
  const coordinates: [number, number][] = []
  let index = 0
  let lat = 0
  let lon = 0

  const nextDelta = (): number => {
    let result = 0
    let shift = 0
    let byte: number
    do {
      if (index >= encoded.length) throw new Error('Malformed polyline')
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20)
    return result & 1 ? ~(result >> 1) : result >> 1
  }

  while (index < encoded.length) {
    lat += nextDelta()
    lon += nextDelta()
    coordinates.push([lon / factor, lat / factor])
  }
  return coordinates
}
