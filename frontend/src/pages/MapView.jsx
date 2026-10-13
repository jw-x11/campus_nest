import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { SpaceRow } from '../components/cards.jsx';
import SpaceMap from '../components/SpaceMap.jsx';
import { LoadingState, ErrorState, EmptyState } from '../components/ui.jsx';
import { formatPrice, searchSpaces } from '../api.js';

// Where the map starts when the user does not share their location.
const GOLETA = { latitude: 34.4358, longitude: -119.8276, zoom: 12 };
const USER_ZOOM = 14;
// If the browser's permission prompt is ignored, show Goleta rather than an empty map.
const LOCATION_WAIT_MS = 10000;

export default function MapView() {
  const [spaces, setSpaces] = useState([]);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [focus, setFocus] = useState(null);
  const [state, setState] = useState('loading');
  // null until we know where to start: the user's position, or Goleta.
  const [view, setView] = useState(() => ('geolocation' in navigator ? null : GOLETA));

  const load = () => {
    setState('loading');
    searchSpaces({ page: 1, pageSize: 25, sortBy: 'post_date', sortOrder: 'desc' })
      .then((data) => {
        setSpaces(data.spaces);
        setTotal(data.total);
        setSelectedId(null);
        setState('ready');
      })
      .catch(() => setState('error'));
  };

  useEffect(() => {
    load();
  }, []);

  // Ask for the user's location as soon as the page opens. A refusal or a failure means Goleta.
  useEffect(() => {
    if (!('geolocation' in navigator)) return undefined;
    const giveUp = setTimeout(() => setView((current) => current ?? GOLETA), LOCATION_WAIT_MS);
    navigator.geolocation.getCurrentPosition(
      (position) =>
        setView({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          zoom: USER_ZOOM,
        }),
      () => setView((current) => current ?? GOLETA),
      { timeout: LOCATION_WAIT_MS, maximumAge: 5 * 60 * 1000 },
    );
    return () => clearTimeout(giveUp);
  }, []);

  const selectedItem = spaces.find((s) => s.id === selectedId);
  const unmapped = spaces.filter((s) => s.latitude == null || s.longitude == null).length;

  // Highlight a listing and zoom the map to its pin. A listing with no coordinates is only highlighted.
  const select = (item) => {
    setSelectedId(item.id);
    if (item.latitude != null && item.longitude != null) {
      // A new object every time, so choosing the same listing again zooms back to it.
      setFocus({ latitude: item.latitude, longitude: item.longitude });
    }
  };

  const selectOnMap = (id) => {
    const item = spaces.find((s) => s.id === id);
    if (!item) return;
    select(item);
    // Bring the matching card into view in the list.
    document.getElementById(`map-card-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  };

  return (
    <div className="mx-auto w-full max-w-[1320px] px-4 pb-16 pt-6 sm:px-5">
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-stone-100 px-4 py-3">
          <span className="flex min-w-0 flex-1 items-center gap-2 text-sm text-stone-500">
            <SearchIcon size={15} /> Map of listed spaces
          </span>
          <span className="font-mono text-xs text-stone-400">
            {total} spaces · showing {spaces.length}
            {unmapped > 0 && ` · ${unmapped} not on the map`}
          </span>
          <div className="flex overflow-hidden rounded-full border border-stone-200 text-[13px]">
            <Link to="/search" className="px-4 py-1.5 text-stone-500 hover:bg-stone-50">List</Link>
            <span className="bg-[#2b2b2b] px-4 py-1.5 font-semibold text-white">Map</span>
          </div>
        </div>

        <div className="grid lg:grid-cols-[380px_1fr]">
          <div className="max-h-[560px] overflow-y-auto border-b border-stone-100 lg:border-b-0 lg:border-r">
            {state === 'loading' && <LoadingState label="Loading spaces…" />}
            {state === 'error' && <ErrorState message="Could not load spaces." onRetry={load} />}
            {state === 'ready' && spaces.length === 0 && (
              <EmptyState title="No spaces to show" body="Try again once listings exist." />
            )}
            {spaces.map((item) => (
              <div
                key={item.id}
                id={`map-card-${item.id}`}
                className={`border-b border-stone-100 last:border-0 ${
                  item.id === selectedId ? 'bg-amber-100/70 shadow-[inset_4px_0_0_#ffd22e]' : 'hover:bg-stone-50'
                }`}
              >
                <SpaceRow item={item} showSave={false} onClick={() => select(item)} />
              </div>
            ))}
          </div>

          <div className="relative min-h-[480px] overflow-hidden bg-[#ecebe4] lg:min-h-[560px]">
            <div className="absolute inset-0">
              {view ? (
                <SpaceMap
                  spaces={spaces}
                  selectedId={selectedId}
                  view={view}
                  focus={focus}
                  onSelect={selectOnMap}
                />
              ) : (
                <LoadingState label="Finding your location…" />
              )}
            </div>

            {selectedItem && (
              <div className="card absolute bottom-4 left-4 z-[5] w-60 p-3 !rounded-2xl shadow-lg">
                <p className="truncate text-sm font-semibold">{selectedItem.title}</p>
                <p className="mt-0.5 font-mono text-[11px] text-stone-400">
                  {selectedItem.location || '—'} · {selectedItem.viewCount} views
                </p>
                <p className="display mt-1">
                  ${formatPrice(selectedItem.price)}
                  <span className="text-xs font-normal text-stone-400">{selectedItem.priceUnit}</span>
                </p>
                <Link
                  to={`/space/${selectedItem.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-sm btn-dark mt-3 w-full justify-center"
                >
                  Show details
                </Link>
              </div>
            )}

            <button onClick={load} className="btn btn-sm absolute left-1/2 top-4 z-[5] -translate-x-1/2 shadow-md">
              ⟳ Search this area
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
