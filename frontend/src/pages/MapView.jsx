import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { SpaceRow } from '../components/cards.jsx';
import { LoadingState, ErrorState, EmptyState } from '../components/ui.jsx';
import { formatPrice, searchSpaces } from '../api.js';

function pinsFromSpaces(spaces) {
  const withGeo = spaces.filter((s) => s.latitude != null && s.longitude != null);
  if (withGeo.length) {
    const lats = withGeo.map((s) => s.latitude);
    const lngs = withGeo.map((s) => s.longitude);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const latSpan = maxLat - minLat || 1;
    const lngSpan = maxLng - minLng || 1;
    return spaces.map((s, i) => {
      if (s.latitude == null || s.longitude == null) {
        return { id: s.id, price: `$${formatPrice(s.price)}`, x: 20 + (i % 4) * 18, y: 28 + Math.floor(i / 4) * 20 };
      }
      return {
        id: s.id,
        price: `$${formatPrice(s.price)}`,
        x: 10 + ((s.longitude - minLng) / lngSpan) * 80,
        y: 14 + (1 - (s.latitude - minLat) / latSpan) * 70,
      };
    });
  }
  return spaces.map((s, i) => ({
    id: s.id,
    price: `$${formatPrice(s.price)}`,
    x: 20 + (i % 4) * 18,
    y: 28 + Math.floor(i / 4) * 20,
  }));
}

export default function MapView() {
  const [spaces, setSpaces] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(0);
  const [state, setState] = useState('loading');

  const load = () => {
    setState('loading');
    searchSpaces({ page: 1, pageSize: 25, sortBy: 'post_date', sortOrder: 'desc' })
      .then((data) => {
        setSpaces(data.spaces);
        setTotal(data.total);
        setSelected(0);
        setState('ready');
      })
      .catch(() => setState('error'));
  };

  useEffect(() => {
    load();
  }, []);

  const pins = useMemo(() => pinsFromSpaces(spaces), [spaces]);
  const selectedItem = spaces[selected];

  return (
    <div className="mx-auto w-full max-w-[1320px] px-4 pb-16 pt-6 sm:px-5">
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-stone-100 px-4 py-3">
          <span className="flex min-w-0 flex-1 items-center gap-2 text-sm text-stone-500">
            <SearchIcon size={15} /> Map of listed spaces
          </span>
          <span className="font-mono text-xs text-stone-400">{total} spaces · showing {spaces.length}</span>
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
            {spaces.map((item, i) => (
              <div
                key={item.id}
                onClick={() => setSelected(i)}
                className={`clickable border-b border-stone-100 last:border-0 ${i === selected ? 'bg-amber-50/60' : 'hover:bg-stone-50'}`}
              >
                <SpaceRow item={item} />
              </div>
            ))}
          </div>

          <div className="relative min-h-[480px] overflow-hidden bg-[#ecebe4] lg:min-h-[560px]">
            {/* subtle street grid backdrop */}
            <div
              className="absolute inset-0 opacity-60"
              style={{
                backgroundImage: 'linear-gradient(#dcdcd2 1px, transparent 1px), linear-gradient(90deg, #dcdcd2 1px, transparent 1px)',
                backgroundSize: '44px 44px',
              }}
            />
            {pins.map((pin, i) => (
              <button
                key={pin.id}
                onClick={() => setSelected(i)}
                className="absolute z-[1] -translate-x-1/2 -translate-y-full"
                style={{ left: `${pin.x}%`, top: `${pin.y}%` }}
              >
                <span className={`block whitespace-nowrap rounded-full border px-3 py-1.5 text-[13px] font-bold shadow-md transition ${
                  i === selected ? 'border-transparent bg-[#2b2b2b] text-white' : 'border-stone-200 bg-white hover:border-stone-400'
                }`}>
                  {pin.price}
                </span>
              </button>
            ))}

            {selectedItem && (
              <Link
                to={`/space/${selectedItem.id}`}
                className="card absolute bottom-14 left-4 z-[2] w-60 p-3 !rounded-2xl shadow-lg transition hover:shadow-xl"
              >
                <p className="truncate text-sm font-semibold">{selectedItem.title}</p>
                <p className="mt-0.5 font-mono text-[11px] text-stone-400">
                  {selectedItem.city} · {selectedItem.viewCount} views
                </p>
                <p className="display mt-1">
                  ${formatPrice(selectedItem.price)}
                  <span className="text-xs font-normal text-stone-400">{selectedItem.priceUnit}</span>
                </p>
              </Link>
            )}

            <p className="absolute bottom-4 left-4 z-[2] rounded-full bg-white/90 px-3 py-1.5 font-mono text-[10.5px] text-stone-500 backdrop-blur">
              Approximate locations · exact address after booking
            </p>
            <button onClick={load} className="btn btn-sm absolute left-1/2 top-4 z-[2] -translate-x-1/2 shadow-md">
              ⟳ Search this area
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
