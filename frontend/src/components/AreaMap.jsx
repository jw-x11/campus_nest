import { useMemo } from 'react';
import { Layer, Map, NavigationControl, Source } from 'react-map-gl/maplibre';
import { maplibregl, MAP_STYLE } from '../maplibre.js';

// The exact address is private until a booking is confirmed, so the map shows an approximate
// area (a circle), not a pin.
// The centre is snapped to a grid about 440 m wide, and the circle is big enough to always
// contain the real spot, so the circle's centre does not give the address away.
const GRID_DEGREES = 0.004;
const RADIUS_METERS = 450;
const METERS_PER_DEGREE = 111320;

function circlePolygon(longitude, latitude, radiusMeters, steps = 64) {
  const latRadius = radiusMeters / METERS_PER_DEGREE;
  const lngRadius = latRadius / Math.cos((latitude * Math.PI) / 180);
  const ring = [];
  for (let i = 0; i <= steps; i += 1) {
    const angle = (i / steps) * 2 * Math.PI;
    ring.push([longitude + lngRadius * Math.cos(angle), latitude + latRadius * Math.sin(angle)]);
  }
  return ring;
}

/**
 * Map of the approximate area around a listing. latitude and longitude are the listing's coordinates.
 * By default the view is fixed; pass interactive for a map the user can pan and zoom.
 */
export default function AreaMap({ latitude, longitude, interactive = false, padding = 80 }) {
  const { area, bounds } = useMemo(() => {
    const centerLat = Math.round(latitude / GRID_DEGREES) * GRID_DEGREES;
    const centerLng = Math.round(longitude / GRID_DEGREES) * GRID_DEGREES;
    const ring = circlePolygon(centerLng, centerLat, RADIUS_METERS);
    const lngs = ring.map((p) => p[0]);
    const lats = ring.map((p) => p[1]);
    return {
      area: { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} },
      bounds: [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ],
    };
  }, [latitude, longitude]);

  return (
    <Map
      mapLib={maplibregl}
      mapStyle={MAP_STYLE}
      initialViewState={{ bounds, fitBoundsOptions: { padding } }}
      // A fixed view has no dragging, zooming, rotating or keyboard control, so scrolling the
      // page over the map scrolls the page.
      interactive={interactive}
      dragRotate={false}
      style={{ width: '100%', height: '100%' }}
    >
      {interactive && <NavigationControl position="top-right" showCompass={false} />}
      <Source id="listing-area" type="geojson" data={area}>
        <Layer id="listing-area-fill" type="fill" paint={{ 'fill-color': '#ffd22e', 'fill-opacity': 0.3 }} />
        <Layer
          id="listing-area-outline"
          type="line"
          paint={{ 'line-color': '#2b2b2b', 'line-width': 2, 'line-opacity': 0.7 }}
        />
      </Source>
    </Map>
  );
}
