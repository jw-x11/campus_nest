import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { ResultRow } from '../components/cards.jsx';
import { Annotation, PageStatus } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { searchSpaces } from '../api.js';

const SORTS = [
  { label: 'Newest', sortBy: 'post_date', sortOrder: 'desc' },
  { label: 'Price ↑', sortBy: 'price', sortOrder: 'asc' },
  { label: 'Price ↓', sortBy: 'price', sortOrder: 'desc' },
];

const PRICE_TYPES = [
  { label: 'Any', key: '' },
  { label: 'Monthly', key: 'recurring_per_month' },
  { label: 'Weekly', key: 'recurring_per_week' },
  { label: 'One-time', key: 'single' },
];

const PAGE_SIZE = 25;
const SLIDER_MAX = 200;

const DEFAULT_QUERY = {
  keyword: '',
  city: '',
  priceType: '',
  maxPrice: SLIDER_MAX,
  availableFrom: '',
  availableTo: '',
  sort: SORTS[0],
};

function CheckRow({ option, onToggle }) {
  return (
    <label
      className="clickable"
      onClick={onToggle}
      style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14 }}
    >
      <span
        style={{
          width: 18,
          height: 18,
          border: '1.5px solid var(--ink)',
          borderRadius: 5,
          display: 'grid',
          placeItems: 'center',
          background: option.active ? 'var(--accent)' : '#fff',
          fontSize: 12,
        }}
      >
        {option.active ? '✓' : ''}
      </span>
      {option.label}
    </label>
  );
}

function toSearchParams(query, page) {
  return {
    keyword: query.keyword,
    city: query.city,
    priceType: query.priceType || undefined,
    maxPrice: query.maxPrice >= SLIDER_MAX ? undefined : query.maxPrice,
    availableFrom: query.availableFrom || undefined,
    availableTo: query.availableTo || undefined,
    sortBy: query.sort.sortBy,
    sortOrder: query.sort.sortOrder,
    page,
    pageSize: PAGE_SIZE,
  };
}

export default function Search() {
  const { showNotes } = useApp();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(DEFAULT_QUERY);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [page, setPage] = useState(1);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const patchDraft = (patch) => setDraft((prev) => ({ ...prev, ...patch }));

  const runSearch = (nextQuery = draft) => {
    setQuery(nextQuery);
    setPage(1);
  };

  const clearAll = () => {
    setDraft(DEFAULT_QUERY);
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    searchSpaces(toSearchParams(query, page))
      .then((data) => {
        if (cancelled) return;
        setResults((prev) => (page === 1 ? data.spaces : [...prev, ...data.spaces]));
        setTotal(data.total);
        setHasMore(data.hasMore);
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load spaces');
        if (page === 1) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, page]);

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '14px 24px',
            borderBottom: '2px solid var(--ink)',
            background: 'var(--tint-2)',
            flexWrap: 'wrap',
          }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              runSearch();
            }}
            className="field"
            style={{ flex: '1 1 280px', borderWidth: 1.5 }}
          >
            <SearchIcon size={16} />
            <input
              value={draft.keyword}
              onChange={(e) => patchDraft({ keyword: e.target.value })}
              placeholder="Search by area, title, or keyword…"
              style={{ border: 'none', outline: 'none', flex: 1, background: 'transparent', fontSize: 14 }}
            />
            <button type="submit" className="chip btn-sm is-active">
              Search
            </button>
          </form>
          <span className="mono" style={{ fontSize: 13, color: 'var(--muted-2)' }}>
            <b style={{ color: 'var(--ink)' }}>{results.length}</b> / {total} spaces
          </span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {SORTS.map((s) => (
              <button
                key={s.label}
                type="button"
                className={`chip btn-sm ${query.sort.label === s.label ? 'is-dark' : ''}`}
                onClick={() => {
                  const next = { ...draft, sort: s };
                  setDraft(next);
                  runSearch(next);
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', border: '1.5px solid var(--ink)', borderRadius: 9, overflow: 'hidden', fontSize: 13 }}>
            <span style={{ padding: '6px 13px', background: 'var(--accent)' }}>List</span>
            <button
              type="button"
              onClick={() => navigate('/map')}
              style={{ padding: '6px 13px', border: 'none', borderLeft: '1.5px solid var(--ink)', background: '#fff', cursor: 'pointer' }}
            >
              Map
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start' }}>
          <aside
            style={{
              flex: 'none',
              width: 262,
              borderRight: '2px solid var(--ink)',
              padding: '22px 22px 40px',
              alignSelf: 'stretch',
            }}
          >
            <div className="section-head" style={{ marginBottom: 18 }}>
              <span style={{ fontSize: 17 }}>Filters</span>
              <button
                type="button"
                className="mono clickable"
                onClick={clearAll}
                style={{ fontSize: 13, color: 'var(--rust)', background: 'none', border: 'none' }}
              >
                Clear all
              </button>
            </div>

            <div className="label" style={{ marginBottom: 11 }}>CITY</div>
            <input
              className="field"
              value={draft.city}
              onChange={(e) => patchDraft({ city: e.target.value })}
              placeholder="Any city"
              style={{ fontSize: 14, padding: '9px 12px' }}
            />

            <div className="label" style={{ margin: '24px 0 11px' }}>PRICE TYPE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
              {PRICE_TYPES.map((o) => (
                <CheckRow
                  key={o.label}
                  option={{ label: o.label, active: draft.priceType === o.key }}
                  onToggle={() => patchDraft({ priceType: o.key })}
                />
              ))}
            </div>

            <div className="label" style={{ margin: '24px 0 12px' }}>
              MAX PRICE · {draft.maxPrice >= SLIDER_MAX ? 'any' : `$${draft.maxPrice}`}
            </div>
            <input
              type="range"
              min={10}
              max={SLIDER_MAX}
              value={draft.maxPrice}
              onChange={(e) => patchDraft({ maxPrice: Number(e.target.value) })}
              style={{ width: '100%', accentColor: 'var(--ink)' }}
            />
            <div
              className="mono"
              style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--label)', marginTop: 7 }}
            >
              <span>$10</span>
              <span>$200+</span>
            </div>

            <div className="label" style={{ margin: '24px 0 11px' }}>AVAILABLE</div>
            <input
              type="date"
              className="field"
              value={draft.availableFrom}
              onChange={(e) => patchDraft({ availableFrom: e.target.value })}
              style={{ fontSize: 13, padding: '9px 12px', marginBottom: 8 }}
            />
            <input
              type="date"
              className="field"
              value={draft.availableTo}
              onChange={(e) => patchDraft({ availableTo: e.target.value })}
              style={{ fontSize: 13, padding: '9px 12px' }}
            />

            <button
              type="button"
              className="btn btn-primary btn-block"
              style={{ marginTop: 22 }}
              onClick={() => runSearch()}
            >
              Search
            </button>

            {showNotes && (
              <Annotation style={{ marginTop: 24 }}>
                Editing filters stays local. Search (or Enter) sends GET /spaces/all with kw, city, price-type, max, from, to, sort.
              </Annotation>
            )}
          </aside>

          <div style={{ flex: 1, minWidth: 0, padding: '6px 0 14px' }}>
            {error && <PageStatus style={{ color: 'var(--rust)' }}>{error}</PageStatus>}
            {!error && !loading && results.length === 0 && (
              <PageStatus>No spaces match these filters.</PageStatus>
            )}
            {results.map((item) => (
              <ResultRow key={item.id} item={item} />
            ))}
            {loading && <PageStatus>{page === 1 ? 'Loading spaces…' : 'Loading more…'}</PageStatus>}
            {!loading && hasMore && (
              <div style={{ padding: 18, display: 'flex', justifyContent: 'center' }}>
                <button type="button" className="btn" onClick={() => setPage((p) => p + 1)}>
                  Load more
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
