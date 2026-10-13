import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { SpaceCard } from '../components/cards.jsx';
import { Field, EmptyState, LoadingState, ErrorState, Pagination } from '../components/ui.jsx';
import { searchSpaces } from '../api.js';
import { stateCode, US_STATES } from '../data.js';

const SORTS = [
  { label: 'Newest', sortBy: 'post_date', sortOrder: 'desc' },
  { label: 'Price ↑', sortBy: 'price', sortOrder: 'asc' },
  { label: 'Price ↓', sortBy: 'price', sortOrder: 'desc' },
];

const PRICE_TYPES = [
  { label: 'Any price', value: '' },
  { label: 'Monthly', value: 'recurring_per_month' },
  { label: 'Weekly', value: 'recurring_per_week' },
  { label: 'One-time', value: 'single' },
];

const PAGE_SIZE = 12;

// Read initial search state from the URL so Back / shared links restore it.
function readFromParams(params) {
  const sort =
    SORTS.find((s) => s.sortBy === params.get('sort') && s.sortOrder === params.get('order')) ||
    SORTS[0];
  return {
    draft: {
      keyword: params.get('kw') || '',
      city: params.get('city') || '',
      // The dropdown only offers state codes, so a hand-typed "California" in the URL becomes "CA".
      state: US_STATES.some((s) => s.value === stateCode(params.get('state'))) ? stateCode(params.get('state')) : '',
      postalCode: params.get('pc') || '',
      priceType: params.get('type') || '',
      minPrice: params.get('min') || '',
      maxPrice: params.get('max') || '',
      availableFrom: params.get('from') || '',
      availableTo: params.get('to') || '',
      sort,
    },
    page: Math.max(1, Number(params.get('pg')) || 1),
  };
}

function toParams(query, page) {
  const p = {};
  if (query.keyword) p.kw = query.keyword;
  if (query.city) p.city = query.city;
  if (query.state) p.state = query.state;
  if (query.postalCode) p.pc = query.postalCode;
  if (query.priceType) p.type = query.priceType;
  if (query.minPrice) p.min = query.minPrice;
  if (query.maxPrice) p.max = query.maxPrice;
  if (query.availableFrom) p.from = query.availableFrom;
  if (query.availableTo) p.to = query.availableTo;
  if (query.sort.label !== SORTS[0].label) {
    p.sort = query.sort.sortBy;
    p.order = query.sort.sortOrder;
  }
  if (page > 1) p.pg = String(page);
  return p;
}

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [initial] = useState(() => readFromParams(params));
  const [draft, setDraft] = useState(initial.draft);
  const [query, setQuery] = useState(initial.draft);
  const [page, setPage] = useState(initial.page);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [state, setState] = useState('loading');

  const patch = (p) => setDraft((d) => ({ ...d, ...p }));

  // Keep the URL in sync (replace, not push) so Back from a listing
  // restores this exact search, and links are shareable.
  useEffect(() => {
    setParams(toParams(query, page), { replace: true });
  }, [query, page, setParams]);

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    searchSpaces({
      keyword: query.keyword || undefined,
      city: query.city || undefined,
      state: query.state || undefined,
      postalCode: query.postalCode || undefined,
      priceType: query.priceType || undefined,
      minPrice: query.minPrice || undefined,
      maxPrice: query.maxPrice || undefined,
      availableFrom: query.availableFrom || undefined,
      availableTo: query.availableTo || undefined,
      sortBy: query.sort.sortBy,
      sortOrder: query.sort.sortOrder,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        if (cancelled) return;
        setResults(data.spaces);
        setTotal(data.total);
        setTotalPages(data.totalPages);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) {
          if (page === 1) setResults([]);
          setState('error');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query, page]);

  const submit = (e) => {
    e?.preventDefault();
    setQuery(draft);
    setPage(1);
  };

  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (query.city) n++;
    if (query.state) n++;
    if (query.postalCode) n++;
    if (query.priceType) n++;
    if (query.minPrice || query.maxPrice) n++;
    if (query.availableFrom || query.availableTo) n++;
    return n;
  }, [query]);

  return (
    <div className="page-wide mx-auto w-full max-w-[1320px] px-4 pb-16 pt-6 sm:px-5">
      <div className="card overflow-hidden">
        {/* toolbar */}
        <div className="flex flex-wrap items-center gap-3 border-b border-stone-100 px-4 py-3 sm:px-5">
          <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2">
            <span className="text-stone-400"><SearchIcon size={16} /></span>
            <input
              value={draft.keyword}
              onChange={(e) => patch({ keyword: e.target.value })}
              placeholder="Search by title or keyword…"
              className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            />
            <button className="btn btn-sm btn-dark" type="submit">Search</button>
          </form>
          <span className="hidden font-mono text-xs text-stone-400 sm:block">
            {totalPages > 0 ? (
              <>Page <b className="text-stone-800">{page}</b> of <b className="text-stone-800">{totalPages}</b> · {total} spaces</>
            ) : (
              <><b className="text-stone-800">{total}</b> spaces</>
            )}
          </span>
          <div className="flex gap-1.5">
            {SORTS.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => {
                  const next = { ...draft, sort: s };
                  setDraft(next);
                  setQuery(next);
                  setPage(1);
                }}
                className={`rounded-full px-3 py-1.5 text-[12.5px] font-medium transition ${
                  query.sort.label === s.label
                    ? 'bg-[#2b2b2b] text-white'
                    : 'bg-stone-100 text-stone-500 hover:bg-stone-200'
                }`}
              >
                {s.label}
              </button>
            ))}
            <Link to="/map" className="rounded-full bg-[#ffd22e] px-3 py-1.5 text-[12.5px] font-semibold">
              Map
            </Link>
          </div>
        </div>

        <div className="flex flex-col lg:flex-row">
          {/* filters */}
          <aside className="w-full flex-none border-b border-stone-100 p-5 lg:w-64 lg:border-b-0 lg:border-r">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold">Filters {activeFilterCount > 0 && (
                <span className="ml-1 rounded-full bg-stone-100 px-2 py-0.5 font-mono text-[11px]">{activeFilterCount}</span>
              )}</h2>
              <button
                type="button"
                className="text-[13px] text-stone-400 hover:text-stone-700"
                onClick={() => {
                  const cleared = {
                    keyword: '', city: '', state: '', postalCode: '', priceType: '',
                    minPrice: '', maxPrice: '', availableFrom: '', availableTo: '', sort: SORTS[0],
                  };
                  setDraft(cleared);
                  setQuery(cleared);
                  setPage(1);
                }}
              >
                Clear all
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
              <Field label="City">
                <input className="input" value={draft.city} onChange={(e) => patch({ city: e.target.value })} placeholder="Any city" />
              </Field>
              <Field label="State">
                <select className="input" value={draft.state} onChange={(e) => patch({ state: e.target.value })}>
                  <option value="">Any state</option>
                  {US_STATES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Postal code">
                <input className="input" value={draft.postalCode} onChange={(e) => patch({ postalCode: e.target.value })} placeholder="Any" />
              </Field>
              <Field label="Price type">
                <select className="input" value={draft.priceType} onChange={(e) => patch({ priceType: e.target.value })}>
                  {PRICE_TYPES.map((o) => (
                    <option key={o.label} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </Field>
              <div className="col-span-2 lg:col-span-1">
                <Field label="Price range (USD)">
                  <div className="flex items-center gap-2">
                    <input type="number" min="0" className="input" placeholder="Min" value={draft.minPrice} onChange={(e) => patch({ minPrice: e.target.value })} />
                    <span className="text-stone-300">–</span>
                    <input type="number" min="0" className="input" placeholder="Max" value={draft.maxPrice} onChange={(e) => patch({ maxPrice: e.target.value })} />
                  </div>
                </Field>
              </div>
              <Field label="Available from">
                <input type="date" className="input" value={draft.availableFrom} onChange={(e) => patch({ availableFrom: e.target.value })} />
              </Field>
              <Field label="Available to">
                <input type="date" className="input" value={draft.availableTo} onChange={(e) => patch({ availableTo: e.target.value })} />
              </Field>
            </div>
            <button className="btn btn-primary btn-block mt-4" onClick={() => submit()} type="button">
              Apply filters
            </button>
          </aside>

          {/* results */}
          <div className="min-w-0 flex-1 p-4 sm:p-5">
            {state === 'loading' && <LoadingState label="Searching spaces…" />}
            {state === 'error' && <ErrorState message="Could not load spaces." onRetry={() => submit()} />}
            {state === 'ready' && results.length === 0 && (
              <EmptyState
                title="No spaces match these filters"
                body="Try a different city, wider dates, or a higher max price."
              />
            )}
            {state === 'ready' && results.length > 0 && (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {results.map((item) => (
                  <SpaceCard key={item.id} item={item} />
                ))}
              </div>
            )}
            {state === 'ready' && (
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
