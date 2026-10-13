import { useEffect, useMemo, useRef, useState } from 'react';
import { Map, Marker, NavigationControl } from 'react-map-gl/maplibre';
import { maplibregl, MAP_STYLE } from '../maplibre.js';
import { formatPrice } from '../api.js';

// Zoom level a clicked pin is brought to, unless the map is already closer.
const PIN_ZOOM = 15;

function hasCoordinates(space) {
  return space.latitude != null && space.longitude != null;
}

/**
 * Map of listings, one price pill per listing that has coordinates.
 * spaces: mapped spaces (see mapSpace). selectedId: id of the highlighted listing.
 * view: { longitude, latitude, zoom } where the map starts. If it changes later, the map flies there.
 * focus: { longitude, latitude } of a listing to zoom to. Pass a new object each time, even for the
 * same listing, so that asking again after the user has moved the map zooms back to it.
 * onSelect(id) runs when a pill is clicked.
 */
export default function SpaceMap({ spaces, selectedId, view, focus, onSelect }) {
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);

  const pins = useMemo(() => spaces.filter(hasCoordinates), [spaces]);

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
      onLoad={() => setReady(true)}
    >
      <NavigationControl position="top-right" showCompass={false} />
      {pins.map((pin) => {
        const selected = String(pin.id) === String(selectedId);
        return (
          <Marker
            key={pin.id}
            longitude={pin.longitude}
            latitude={pin.latitude}
            anchor="bottom"
            style={{ zIndex: selected ? 2 : 1 }}
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              onSelect?.(pin.id);
            }}
          >
            <button
              type="button"
              aria-label={`${pin.title}, $${formatPrice(pin.price)}`}
              className={`block cursor-pointer whitespace-nowrap rounded-full border px-3 py-1.5 text-[13px] font-bold shadow-md transition ${
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
