import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SpaceCard } from '../components/cards.jsx';
import { EmptyState, LoadingState, ErrorState } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';

export default function Saved() {
  const { savedItems, refreshSaved } = useApp();
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    refreshSaved()
      .then(() => {
        if (!cancelled) setState('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load saved spaces.');
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [refreshSaved]);

  return (
    <div className="page">
      <p className="eyebrow">Watchlist</p>
      <h1 className="display mt-1 text-3xl">Saved spaces</h1>
      <p className="mt-1 text-sm text-stone-500">
        {savedItems.length} space{savedItems.length === 1 ? '' : 's'} saved
      </p>

      <div className="mt-5">
        {state === 'loading' && <div className="card"><LoadingState label="Loading saved spaces…" /></div>}
        {state === 'error' && <div className="card"><ErrorState message={error} onRetry={() => window.location.reload()} /></div>}
        {state === 'ready' && savedItems.length === 0 && (
          <div className="card">
            <EmptyState
              title="Nothing saved yet"
              body="Tap the heart on any listing to keep it here."
              action={<Link to="/search" className="btn btn-primary">Browse spaces</Link>}
            />
          </div>
        )}
        {state === 'ready' && savedItems.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {savedItems.map((item) => (
              <SpaceCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
