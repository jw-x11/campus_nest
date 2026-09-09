import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchIcon, RefreshIcon } from '../components/icons.jsx';
import { Hatch, Annotation, PageStatus } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
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
        return { id: s.id, price: `$${formatPrice(s.price)}`, x: 22 + (i % 4) * 18, y: 30 + Math.floor(i / 4) * 20 };
      }
      return {
        id: s.id,
        price: `$${formatPrice(s.price)}`,
        x: 12 + ((s.longitude - minLng) / lngSpan) * 76,
        y: 18 + (1 - (s.latitude - minLat) / latSpan) * 64,
      };
    });
  }
  return spaces.map((s, i) => ({
    id: s.id,
    price: `$${formatPrice(s.price)}`,
    x: 22 + (i % 4) * 18,
    y: 30 + Math.floor(i / 4) * 20,
  }));
}

export default function MapView() {
  const navigate = useNavigate();
  const { showNotes } = useApp();
  const [spaces, setSpaces] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(0);
  const [searchVisible, setSearchVisible] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    searchSpaces({ page: 1, pageSize: 25, sortBy: 'post_date', sortOrder: 'desc' })
      .then((data) => {
        setSpaces(data.spaces);
        setTotal(data.total);
        setSelected(0);
        setError('');
      })
      .catch((err) => setError(err.message || 'Could not load spaces'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const pins = useMemo(() => pinsFromSpaces(spaces), [spaces]);
  const selectedItem = spaces[selected];
  const selectedPin = pins[selected];

  return (
    <div className="page page-wide">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '13px 24px', borderBottom: '2px solid var(--ink)', flexWrap: 'wrap' }}>
          <div className="field" style={{ flex: '1 1 320px', maxWidth: 520, borderWidth: 1.5, padding: '8px 8px 8px 14px' }}>
            <SearchIcon size={16} />
            <span style={{ flex: 1, fontSize: 14 }}>All listed spaces</span>
            <button className="chip btn-sm is-active" onClick={load}>Search</button>
          </div>
          <div style={{ display: 'flex', border: '1.5px solid var(--ink)', borderRadius: 9, overflow: 'hidden', fontSize: 13 }}>
            <button onClick={() => navigate('/search')} style={{ padding: '7px 14px', border: 'none', background: '#fff', cursor: 'pointer' }}>
              List
            </button>
            <span style={{ padding: '7px 14px', background: 'var(--accent)', borderLeft: '1.5px solid var(--ink)' }}>Map</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '12px 24px', borderBottom: '1.5px solid var(--line-2)', flexWrap: 'wrap' }}>
          <span className="mono" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--label)' }}>
            {total} spaces · showing {spaces.length}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'stretch', height: 560 }}>
          <div style={{ flex: 'none', width: 420, borderRight: '2px solid var(--ink)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div className="label" style={{ padding: '14px 18px 8px' }}>SPACES IN THIS AREA</div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {loading && <PageStatus>Loading spaces…</PageStatus>}
              {error && <PageStatus style={{ color: 'var(--rust)' }}>{error}</PageStatus>}
              {!loading && spaces.length === 0 && <PageStatus>No spaces to show on the map.</PageStatus>}
              {spaces.map((item, i) => (
                <div
                  key={item.id}
                  onClick={() => setSelected(i)}
                  className="clickable"
                  style={{
                    display: 'flex',
                    gap: 13,
                    padding: '14px 18px',
                    borderBottom: '1.5px solid var(--line-2)',
                    background: i === selected ? 'var(--tint)' : '#fff',
                  }}
                >
                  <Hatch style={{ flex: 'none', width: 96, height: 74, border: '1.5px solid var(--ink)', borderRadius: 10 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontSize: 15 }}>{item.title}</span>
                      <span className="display" style={{ fontSize: 17, whiteSpace: 'nowrap' }}>
                        ${formatPrice(item.price)}<span style={{ fontSize: 11, color: 'var(--label)' }}>{item.priceUnit}</span>
                      </span>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--label)', marginTop: 5 }}>
                      {item.city} · {item.priceTypeLabel}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, border: '1.5px solid var(--ink)', borderRadius: 6, padding: '2px 9px' }}>
                        {item.priceTypeLabel}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--muted-2)' }}>{item.viewCount} views</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="map-grid" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 0, right: 0, top: '33%', height: 14, background: 'var(--tint)', borderTop: '1.5px solid #d2d3ca', borderBottom: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', left: 0, right: 0, top: '68%', height: 10, background: 'var(--tint)', borderTop: '1.5px solid #d2d3ca', borderBottom: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '43%', width: 14, background: 'var(--tint)', borderLeft: '1.5px solid #d2d3ca', borderRight: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '78%', width: 10, background: 'var(--tint)', borderLeft: '1.5px solid #d2d3ca', borderRight: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', left: '6%', top: '74%', width: 90, height: 60, background: '#dfe7d4', border: '1.5px solid #cdd6bf', borderRadius: 6 }} />

            {pins.map((pin, i) => {
              const isSel = i === selected;
              return (
                <div
                  key={pin.id}
                  onClick={() => setSelected(i)}
                  className="clickable"
                  style={{ position: 'absolute', left: `${pin.x}%`, top: `${pin.y}%`, transform: 'translate(-50%,-100%)', zIndex: isSel ? 5 : 1 }}
                >
                  <div
                    className="display"
                    style={{
                      background: isSel ? 'var(--ink)' : '#fff',
                      color: isSel ? '#fff' : 'var(--ink)',
                      border: '2px solid var(--ink)',
                      borderRadius: 999,
                      padding: '6px 13px',
                      fontSize: 15,
                      boxShadow: '0 2px 5px rgba(0,0,0,.18)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {pin.price}
                  </div>
                  <div style={{ width: 0, height: 0, margin: '0 auto', borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: '7px solid var(--ink)' }} />
                </div>
              );
            })}

            {selectedPin && selectedItem && <SelectedCallout pin={selectedPin} item={selectedItem} />}

            {searchVisible && (
              <button
                onClick={() => {
                  setSearchVisible(false);
                  load();
                }}
                style={{
                  position: 'absolute',
                  top: 18,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: '#fff',
                  border: '2px solid var(--ink)',
                  borderRadius: 999,
                  padding: '9px 18px',
                  fontSize: 14,
                  fontWeight: 600,
                  boxShadow: '0 3px 9px rgba(0,0,0,.18)',
                  cursor: 'pointer',
                }}
              >
                <RefreshIcon size={15} /> Search this area
              </button>
            )}

            <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', alignItems: 'center', gap: 7, background: '#fff', border: '1.5px solid var(--ink)', borderRadius: 9, padding: '7px 11px' }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', border: '2px solid var(--rust)' }} />
              <span className="mono" style={{ fontSize: 11, color: 'var(--muted-2)' }}>
                Approximate locations · exact address after booking
              </span>
            </div>

            <div style={{ position: 'absolute', bottom: 16, right: 16, display: 'flex', flexDirection: 'column', border: '1.5px solid var(--ink)', borderRadius: 9, overflow: 'hidden', background: '#fff' }}>
              <span className="clickable" style={{ padding: '8px 12px', fontSize: 18, textAlign: 'center', borderBottom: '1.5px solid var(--ink)' }}>+</span>
              <span className="clickable" style={{ padding: '8px 12px', fontSize: 18, textAlign: 'center' }}>−</span>
            </div>
          </div>
        </div>

        {showNotes && (
          <div style={{ padding: '14px 24px', borderTop: '1.5px solid var(--line-2)' }}>
            <Annotation>
              Pins are placed from listing lat/lng when present, otherwise laid out in a grid. A dedicated /spaces/map bbox endpoint is not in the MVP yet.
            </Annotation>
          </div>
        )}
      </div>
    </div>
  );
}

function SelectedCallout({ pin, item }) {
  return (
    <div
      style={{
        position: 'absolute',
        left: `${pin.x}%`,
        top: `${pin.y}%`,
        transform: 'translate(-50%, calc(-100% - 34px))',
        width: 230,
        background: '#fff',
        border: '2px solid var(--ink)',
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: '0 6px 16px rgba(0,0,0,.18)',
        zIndex: 6,
        pointerEvents: 'none',
      }}
    >
      <Hatch style={{ height: 96, borderBottom: '1.5px solid var(--ink)' }} />
      <div style={{ padding: '11px 13px 13px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 14 }}>{item.title}</span>
          <span className="display" style={{ fontSize: 16 }}>
            {pin.price}<span style={{ fontSize: 10, color: 'var(--label)' }}>{item.priceUnit}</span>
          </span>
        </div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--label)', marginTop: 5 }}>
          {item.city} · {item.viewCount} views
        </div>
      </div>
    </div>
  );
}
