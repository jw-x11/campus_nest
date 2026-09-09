import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Hatch, Annotation, PageStatus } from '../components/ui.jsx';
import { HeartIcon } from '../components/icons.jsx';
import { useApp } from '../context/AppContext.jsx';
import { formatPrice } from '../api.js';

export default function Saved() {
  const navigate = useNavigate();
  const { savedItems, toggleSaved, refreshSaved, showNotes } = useApp();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    refreshSaved()
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load saved spaces');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshSaved]);

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to="/search" style={{ fontSize: 13.5, color: 'var(--muted)' }}>← Back to search</Link>
        </div>

        <div style={{ padding: '30px 40px 40px' }}>
          <div className="section-head" style={{ marginBottom: 6 }}>
            <div>
              <h1 className="display" style={{ fontSize: 30 }}>Saved spaces</h1>
              <div style={{ fontSize: 14.5, color: 'var(--muted)', marginTop: 5 }}>
                {savedItems.length} {savedItems.length === 1 ? 'space' : 'spaces'} on your watchlist
              </div>
            </div>
          </div>

          {loading && <PageStatus>Loading saved spaces…</PageStatus>}
          {error && <PageStatus style={{ color: 'var(--rust)' }}>{error}</PageStatus>}

          {!loading && !error && savedItems.length === 0 ? (
            <PageStatus>
              Nothing saved yet — <Link to="/search" style={{ color: 'var(--rust)' }}>browse spaces</Link>.
            </PageStatus>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 18, marginTop: 24 }}>
              {savedItems.map((item) => (
                <div
                  key={item.id}
                  className="clickable"
                  onClick={() => navigate(`/space/${item.id}`)}
                  style={{
                    display: 'flex',
                    gap: 16,
                    border: '1.5px solid var(--ink)',
                    borderRadius: 14,
                    overflow: 'hidden',
                    padding: 14,
                  }}
                >
                  <Hatch style={{ position: 'relative', flex: 'none', width: 148, height: 120, border: '1.5px solid var(--ink)', borderRadius: 11 }}>
                    <span className="tag" style={{ position: 'absolute', top: 8, left: 8 }}>{item.typeLabel}</span>
                  </Hatch>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontSize: 16 }}>{item.title}</span>
                      <button
                        aria-label="Remove from saved"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSaved(item.id);
                        }}
                        style={{ flex: 'none', width: 30, height: 30, border: '1.5px solid var(--ink)', borderRadius: 999, display: 'grid', placeItems: 'center', background: 'var(--accent)', cursor: 'pointer' }}
                      >
                        <HeartIcon size={15} filled />
                      </button>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--label)', marginTop: 5 }}>
                      {item.city} · {item.priceTypeLabel}
                    </div>
                    <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', paddingTop: 11 }}>
                      <span className="display" style={{ fontSize: 21 }}>
                        ${formatPrice(item.price)}<span style={{ fontSize: 12, color: 'var(--label)' }}>{item.priceUnit}</span>
                      </span>
                      <span style={{ fontSize: 13, color: 'var(--muted-2)' }}>{item.viewCount} views</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {showNotes && (
            <Annotation style={{ marginTop: 22 }}>
              Hearts call POST/DELETE /saved/{'{space_id}'}. This list is GET /saved/list.
            </Annotation>
          )}
        </div>
      </div>
    </div>
  );
}
