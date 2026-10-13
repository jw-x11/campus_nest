import * as maplibregl from 'maplibre-gl';
// MapLibre GL v6 does not bundle its worker; Vite emits it as a separate file and gives us its URL.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

// Must run before the first map is created. Every map component imports this file.
maplibregl.setWorkerUrl(maplibreWorkerUrl);

// Full style.json URL including the API key, e.g. Geoapify's Klokantech Basic:
// https://maps.geoapify.com/v1/styles/klokantech-basic/style.json?apiKey=YOUR_KEY
// Without it, fall back to the public OpenStreetMap tiles so the map still works in development.
const FALLBACK_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
};

export const MAP_STYLE = import.meta.env.VITE_MAP_STYLE_URL || FALLBACK_STYLE;

export { maplibregl };
