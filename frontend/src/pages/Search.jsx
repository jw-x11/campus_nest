import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchIcon } from '../components/icons.jsx';
import { ResultRow } from '../components/cards.jsx';
import { Annotation } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import {
  listings,
  initialTypeFilters,
  initialPriceTypeFilters,
} from '../data.js';

const SORTS = ['Best match', 'Price ↑', 'Top rated'];

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

export default function Search() {
  const { showNotes } = useApp();
  const navigate = useNavigate();
  const [types, setTypes] = useState(initialTypeFilters);
  const [priceTypes, setPriceTypes] = useState(initialPriceTypeFilters);
  const [maxPrice, setMaxPrice] = useState(90);
  const [sort, setSort] = useState('Best match');

  const toggle = (setter) => (i) =>
    setter((prev) => prev.map((o, j) => (j === i ? { ...o, active: !o.active } : o)));

  const clearAll = () => {
    setTypes((p) => p.map((o) => ({ ...o, active: false })));
    setPriceTypes((p) => p.map((o) => ({ ...o, active: false })));
    setMaxPrice(200);
  };

  const results = useMemo(() => {
    const activeTypes = types.filter((t) => t.active).map((t) => t.label);
    const activePT = priceTypes.filter((t) => t.active).map((t) => t.key);
    let out = listings.filter((l) => {
      if (activeTypes.length && !activeTypes.includes(l.typeLabel)) return false;
      if (activePT.length && !activePT.includes(l.priceType)) return false;
      if (l.price > maxPrice) return false;
      return true;
    });
    if (sort === 'Price ↑') out = [...out].sort((a, b) => a.price - b.price);
    else if (sort === 'Top rated') out = [...out].sort((a, b) => b.rating - a.rating);
    return out;
  }, [types, priceTypes, maxPrice, sort]);

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* search subheader */}
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
          <div className="field" style={{ flex: '1 1 280px', borderWidth: 1.5 }}>
            <SearchIcon size={16} />
            <span className="mono" style={{ fontSize: 14, color: 'var(--label)' }}>
              Search by area, type, or keyword…
            </span>
          </div>
          <span className="mono" style={{ fontSize: 13, color: 'var(--muted-2)' }}>
            <b style={{ color: 'var(--ink)' }}>{results.length}</b> / 128 spaces
          </span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {SORTS.map((s) => (
              <button
                key={s}
                className={`chip btn-sm ${sort === s ? 'is-dark' : ''}`}
                onClick={() => setSort(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', border: '1.5px solid var(--ink)', borderRadius: 9, overflow: 'hidden', fontSize: 13 }}>
            <span style={{ padding: '6px 13px', background: 'var(--accent)' }}>List</span>
            <button
              onClick={() => navigate('/map')}
              style={{ padding: '6px 13px', border: 'none', borderLeft: '1.5px solid var(--ink)', background: '#fff', cursor: 'pointer' }}
            >
              Map
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start' }}>
          {/* filter sidebar */}
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
                className="mono clickable"
                onClick={clearAll}
                style={{ fontSize: 13, color: 'var(--rust)', background: 'none', border: 'none' }}
              >
                Clear all
              </button>
            </div>

            <div className="label" style={{ marginBottom: 11 }}>SPACE TYPE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
              {types.map((o, i) => (
                <CheckRow key={o.label} option={o} onToggle={() => toggle(setTypes)(i)} />
              ))}
            </div>

            <div className="label" style={{ margin: '24px 0 11px' }}>PRICE TYPE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
              {priceTypes.map((o, i) => (
                <CheckRow key={o.label} option={o} onToggle={() => toggle(setPriceTypes)(i)} />
              ))}
            </div>

            <div className="label" style={{ margin: '24px 0 12px' }}>
              MAX PRICE · ${maxPrice}/mo
            </div>
            <input
              type="range"
              min={10}
              max={200}
              value={maxPrice}
              onChange={(e) => setMaxPrice(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--ink)' }}
            />
            <div
              className="mono"
              style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--label)', marginTop: 7 }}
            >
              <span>$10</span>
              <span>$200+</span>
            </div>

            {showNotes && (
              <Annotation style={{ marginTop: 24 }}>
                Filters live-update the result count + list. Sticky on scroll.
              </Annotation>
            )}
          </aside>

          {/* results */}
          <div style={{ flex: 1, minWidth: 0, padding: '6px 0 14px' }}>
            {results.length === 0 ? (
              <div style={{ padding: '48px 22px', color: 'var(--muted)', textAlign: 'center' }}>
                No spaces match these filters.
              </div>
            ) : (
              results.map((item) => <ResultRow key={item.id} item={item} />)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
