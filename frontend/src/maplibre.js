import * as maplibregl from 'maplibre-gl';
// MapLibre GL v6 does not bundle its worker; Vite emits it as a separate file and gives us its URL.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

// Must run before the first map is created. Every map component imports this file.
maplibregl.setWorkerUrl(maplibreWorkerUrl);

// Full style.json URL including the API key, e.g. Geoapify's Klokantech Basic:
// https://maps.geoapify.com/v1/styles/klokantech-basic/style.json?apiKey=YOUR_KEY
// Or a raster tile URL template with {z}/{x}/{y}, e.g. https://maps.geoapify.com/v1/tile/carto/{z}/{x}/{y}.png?apiKey=YOUR_KEY
// Without either (or with no key filled in), use the fallback tile URL from VITE_MAP_FALLBACK_TILE_URL,
// which defaults to the public OpenStreetMap tiles so the map still works in development.
const DEFAULT_FALLBACK_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

function rasterStyle(tileUrl, attribution) {
  return {
    version: 8,
    sources: {
      tiles: { type: 'raster', tiles: [tileUrl], tileSize: 256, maxzoom: 19, attribution },
    },
    layers: [{ id: 'tiles', type: 'raster', source: 'tiles' }],
  };
}

const OSM_ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// A URL counts as configured only when it is set and its key is filled in. An empty value, a bare
// "apiKey=" or the "YOUR_KEY" placeholder from .env.example means no key, so the fallback is used.
function configured(url) {
  const value = (url || '').trim();
  if (!value) return null;
  const key = /[?&]apiKey=([^&]*)/i.exec(value);
  if (key && (!key[1] || key[1] === 'YOUR_KEY')) return null;
  return value;
}

const STYLE_URL = configured(import.meta.env.VITE_MAP_STYLE_URL);
const TILE_URL = configured(import.meta.env.VITE_MAP_TILE_URL);
const FALLBACK_TILE_URL = configured(import.meta.env.VITE_MAP_FALLBACK_TILE_URL) || DEFAULT_FALLBACK_TILES;
const FALLBACK_ATTRIBUTION = (import.meta.env.VITE_MAP_FALLBACK_ATTRIBUTION || '').trim() || OSM_ATTRIBUTION;

export const MAP_STYLE =
  STYLE_URL ||
  (TILE_URL
    ? rasterStyle(
        TILE_URL,
        `© <a href="https://www.geoapify.com/">Geoapify</a> ${OSM_ATTRIBUTION}`,
      )
    : rasterStyle(FALLBACK_TILE_URL, FALLBACK_ATTRIBUTION));

export { maplibregl };
