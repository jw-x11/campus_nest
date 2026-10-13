import { useEffect, useMemo, useRef, useState } from 'react';
import { Map, Marker, NavigationControl } from 'react-map-gl/maplibre';
import { maplibregl, MAP_STYLE } from '../maplibre.js';
import { formatPrice } from '../api.js';

const INITIAL_VIEW = { longitude: -98.58, latitude: 39.83, zoom: 3 };

function hasCoordinates(space) {
  return space.latitude != null && space.longitude != null;
}

/**
 * Map of listings, one price pill per listing that has coordinates.
 * spaces: mapped spaces (see mapSpace). selectedId: id of the highlighted listing.
 * onSelect(id) runs when a pill is clicked.
 */
export default function SpaceMap({ spaces, selectedId, onSelect }) {
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);
  const pins = useMemo(() => spaces.filter(hasCoordinates), [spaces]);

  // Zoom to fit every pin whenever the listings change.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || pins.length === 0) return;
    if (pins.length === 1) {
      map.jumpTo({ center: [pins[0].longitude, pins[0].latitude], zoom: 14 });
      return;
    }
    const lngs = pins.map((p) => p.longitude);
    const lats = pins.map((p) => p.latitude);
    map.fitBounds(
      [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ],
      { padding: 70, maxZoom: 15, duration: 0 },
    );
  }, [ready, pins]);

  return (
    <Map
      ref={mapRef}
      mapLib={maplibregl}
      mapStyle={MAP_STYLE}
      initialViewState={INITIAL_VIEW}
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
