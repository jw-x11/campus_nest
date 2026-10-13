import { Map, Marker, NavigationControl } from 'react-map-gl/maplibre';
import { maplibregl, MAP_STYLE } from '../maplibre.js';

/**
 * Map with a pin at a listing's exact coordinates.
 * By default the view is fixed; pass interactive for a map the user can pan and zoom.
 * zoom is the starting zoom level.
 */
export default function ListingMap({ latitude, longitude, interactive = false, zoom = 15 }) {
  return (
    <Map
      mapLib={maplibregl}
      mapStyle={MAP_STYLE}
      initialViewState={{ latitude, longitude, zoom }}
      // A fixed view has no dragging, zooming, rotating or keyboard control, so scrolling the
      // page over the map scrolls the page.
      interactive={interactive}
      dragRotate={false}
      style={{ width: '100%', height: '100%' }}
    >
      {interactive && <NavigationControl position="top-right" showCompass={false} />}
      <Marker latitude={latitude} longitude={longitude} anchor="bottom">
        <svg
          width="32"
          height="42"
          viewBox="0 0 32 42"
          role="img"
          aria-label="Listing location"
          className="drop-shadow-md"
        >
          <path
            d="M16 1C8 1 1.5 7.4 1.5 15.3 1.5 26 16 41 16 41S30.5 26 30.5 15.3C30.5 7.4 24 1 16 1Z"
            fill="#ffd22e"
            stroke="#2b2b2b"
            strokeWidth="2"
          />
          <circle cx="16" cy="15" r="5" fill="#2b2b2b" />
        </svg>
      </Marker>
    </Map>
  );
}
