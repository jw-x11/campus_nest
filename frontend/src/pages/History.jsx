import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SpaceRow } from '../components/cards.jsx';
import { EmptyState, LoadingState, ErrorState } from '../components/ui.jsx';
import { clearHistory, deleteHistory, listHistory } from '../api.js';

export default function History() {
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState('loading');

  const load = useCallback(async (nextCursor) => {
    setState('loading');
    try {
      const data = await listHistory({ cursor: nextCursor || undefined, pageSize: 12 });
      setItems((prev) => (nextCursor ? [...prev, ...data.items] : data.items));
      setCursor(data.nextCursor);
      setHasMore(data.hasMore);
      setTotal(data.total);
      setState('ready');
    } catch {
      if (!nextCursor) setState('error');
      else setState('ready');
    }
  }, []);

  useEffect(() => {
    load(null);
  }, [load]);

  const remove = async (id) => {
    await deleteHistory(id).catch(() => {});
    setItems((prev) => prev.filter((i) => String(i.id) !== String(id)));
  };

  const clear = async () => {
    await clearHistory().catch(() => {});
    setItems([]);
    setCursor(null);
    setHasMore(false);
    setTotal(0);
  };

  return (
    <div className="page !max-w-[860px]">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Browsing</p>
          <h1 className="display mt-1 text-3xl">Recently viewed</h1>
          <p className="mt-1 font-mono text-xs text-stone-400">{total} spaces</p>
        </div>
        {items.length > 0 && (
          <button className="btn btn-sm" onClick={clear}>Clear all</button>
        )}
      </div>

      <div className="card">
        {state === 'loading' && items.length === 0 && <LoadingState label="Loading history…" />}
        {state === 'error' && <ErrorState message="Could not load history." onRetry={() => load(null)} />}
        {state === 'ready' && items.length === 0 && (
          <EmptyState
            title="No recent views"
            body="Spaces you open while logged in will show up here."
            action={<Link to="/search" className="btn btn-primary">Browse spaces</Link>}
          />
        )}
        {items.map((item) => (
          <div key={`${item.id}-${item.viewedAt}`} className="relative">
            <SpaceRow item={item} />
            <button
              onClick={() => remove(item.id)}
              aria-label="Remove from history"
              className="absolute right-4 top-4 font-mono text-[11px] text-stone-300 hover:text-stone-600"
            >
              Remove
            </button>
          </div>
        ))}
        {state === 'ready' && hasMore && (
          <div className="flex justify-center p-4">
            <button className="btn btn-sm" onClick={() => load(cursor)}>Load more</button>
          </div>
        )}
      </div>
    </div>
  );
}
