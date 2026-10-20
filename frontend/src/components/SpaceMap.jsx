import { useEffect, useRef, useState } from 'react';
import { Map, Marker, NavigationControl } from 'react-map-gl/maplibre';
import { maplibregl, MAP_STYLE } from '../maplibre.js';
import { formatPrice } from '../api.js';

// Zoom level a clicked pin is brought to, unless the map is already closer.
const PIN_ZOOM = 15;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

// The visible area as { south, north, west, east }, kept on the globe even when the map is
// zoomed out far enough to repeat the world sideways.
function visibleBounds(map) {
  const bounds = map.getBounds();
  return {
    south: clamp(bounds.getSouth(), -90, 90),
    north: clamp(bounds.getNorth(), -90, 90),
    west: clamp(bounds.getWest(), -180, 180),
    east: clamp(bounds.getEast(), -180, 180),
  };
}

/**
 * Map of listings, one price pill per pin.
 * pins: [{ id, title, latitude, longitude, price }]. selectedId: id of the highlighted listing.
 * hoveredId: id of the listing whose card is under the mouse; its pin grows a little.
 * view: { longitude, latitude, zoom } where the map starts. If it changes later, the map flies there.
 * focus: { longitude, latitude } of a listing to zoom to. Pass a new object each time, even for the
 * same listing, so that asking again after the user has moved the map zooms back to it.
 * onSelect(id) runs when a pill is clicked.
 * onBoundsChange({ south, north, west, east }, byUser) runs when the map loads and after every move.
 * byUser is true when the user panned or zoomed, false for the map's own flights to view or focus.
 * onMoveStart() runs when any move begins.
 */
export default function SpaceMap({ pins, selectedId, hoveredId, view, focus, onSelect, onBoundsChange, onMoveStart }) {
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);

  // Move to a new starting view, for example when the user's location arrives after the map opened.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.flyTo({ center: [view.longitude, view.latitude], zoom: view.zoom, duration: 1200 });
  }, [ready, view]);

  // Zoom in on the listing the parent asked for.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !focus) return;
    map.flyTo({
      center: [focus.longitude, focus.latitude],
      zoom: Math.max(map.getZoom(), PIN_ZOOM),
      duration: 800,
    });
  }, [ready, focus]);

  return (
    <Map
      ref={mapRef}
      mapLib={maplibregl}
      mapStyle={MAP_STYLE}
      initialViewState={view}
      style={{ width: '100%', height: '100%' }}
      onLoad={(e) => {
        setReady(true);
        onBoundsChange?.(visibleBounds(e.target), false);
      }}
      onMoveStart={() => onMoveStart?.()}
      // Dragging, scrolling and the zoom buttons carry the browser event; flyTo does not.
      onMoveEnd={(e) => onBoundsChange?.(visibleBounds(e.target), Boolean(e.originalEvent))}
    >
      <NavigationControl position="top-right" showCompass={false} />
      {pins.map((pin) => {
        const selected = String(pin.id) === String(selectedId);
        const hovered = String(pin.id) === String(hoveredId);
        return (
          <Marker
            key={pin.id}
            longitude={pin.longitude}
            latitude={pin.latitude}
            anchor="bottom"
            style={{ zIndex: hovered ? 3 : selected ? 2 : 1 }}
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              onSelect?.(pin.id);
            }}
          >
            <button
              type="button"
              aria-label={`${pin.title}, $${formatPrice(pin.price)}`}
              // Grows from its bottom point, so the pill stays anchored on the listing.
              className={`block origin-bottom cursor-pointer whitespace-nowrap rounded-full border px-3 py-1.5 text-[13px] font-bold shadow-md transition duration-150 ${
                hovered ? 'scale-125 shadow-lg' : ''
              } ${
                selected ? 'border-transparent bg-[#2b2b2b] text-white' : 'border-stone-200 bg-white hover:border-stone-400'
              }`}
            >
              ${formatPrice(pin.price)}
            </button>
          </Marker>
        );
      })}
    </Map>
  );
}
