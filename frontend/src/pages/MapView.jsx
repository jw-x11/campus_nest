import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { SpaceRow } from '../components/cards.jsx';
import SpaceMap from '../components/SpaceMap.jsx';
import { LoadingState, ErrorState, EmptyState } from '../components/ui.jsx';
import { formatPrice, searchSpaces } from '../api.js';

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

  const selectedItem = spaces[selected];
  const unmapped = spaces.filter((s) => s.latitude == null || s.longitude == null).length;

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
            <div className="absolute inset-0">
              <SpaceMap
                spaces={spaces}
                selectedId={selectedItem?.id}
                onSelect={(id) => {
                  const index = spaces.findIndex((s) => s.id === id);
                  if (index >= 0) setSelected(index);
                }}
              />
            </div>

            {selectedItem && (
              <Link
                to={`/space/${selectedItem.id}`}
                className="card absolute bottom-14 left-4 z-[5] w-60 p-3 !rounded-2xl shadow-lg transition hover:shadow-xl"
              >
                <p className="truncate text-sm font-semibold">{selectedItem.title}</p>
                <p className="mt-0.5 font-mono text-[11px] text-stone-400">
                  {[selectedItem.city, selectedItem.state].filter(Boolean).join(', ')} · {selectedItem.viewCount} views
                </p>
                <p className="display mt-1">
                  ${formatPrice(selectedItem.price)}
                  <span className="text-xs font-normal text-stone-400">{selectedItem.priceUnit}</span>
                </p>
              </Link>
            )}

            <p className="absolute bottom-4 left-4 z-[5] rounded-full bg-white/90 px-3 py-1.5 font-mono text-[10.5px] text-stone-500 backdrop-blur">
              Approximate locations · exact address after booking
              {unmapped > 0 && ` · ${unmapped} not on the map`}
            </p>
            <button onClick={load} className="btn btn-sm absolute left-1/2 top-4 z-[5] -translate-x-1/2 shadow-md">
              ⟳ Search this area
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
