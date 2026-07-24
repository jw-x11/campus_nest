import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchIcon, RefreshIcon } from '../components/icons.jsx';
import { Hatch, Annotation } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { listings, mapPins } from '../data.js';

const FILTERS = ['Space type ▾', 'Price type ▾', 'Max price ▾', 'Access ▾'];

export default function MapView() {
  const navigate = useNavigate();
  const { showNotes } = useApp();
  const mapList = listings.slice(0, 4);
  const [selected, setSelected] = useState(0);
  const [searchVisible, setSearchVisible] = useState(true);

  return (
    <div className="page page-wide">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* sub nav */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '13px 24px', borderBottom: '2px solid var(--ink)', flexWrap: 'wrap' }}>
          <div className="field" style={{ flex: '1 1 320px', maxWidth: 520, borderWidth: 1.5, padding: '8px 8px 8px 14px' }}>
            <SearchIcon size={16} />
            <span style={{ flex: 1, fontSize: 14 }}>Berkeley · Jun 1 – Aug 20</span>
            <span className="chip btn-sm is-active">Search</span>
          </div>
          <div style={{ display: 'flex', border: '1.5px solid var(--ink)', borderRadius: 9, overflow: 'hidden', fontSize: 13 }}>
            <button onClick={() => navigate('/search')} style={{ padding: '7px 14px', border: 'none', background: '#fff', cursor: 'pointer' }}>
              List
            </button>
            <span style={{ padding: '7px 14px', background: 'var(--accent)', borderLeft: '1.5px solid var(--ink)' }}>Map</span>
          </div>
        </div>

        {/* filter chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '12px 24px', borderBottom: '1.5px solid var(--line-2)', flexWrap: 'wrap' }}>
          {FILTERS.map((f) => (
            <span key={f} className="chip btn-sm">{f}</span>
          ))}
          <span className="mono" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--label)' }}>
            128 spaces in view · showing 4 nearest
          </span>
        </div>

        {/* split */}
        <div style={{ display: 'flex', alignItems: 'stretch', height: 560 }}>
          {/* list */}
          <div style={{ flex: 'none', width: 420, borderRight: '2px solid var(--ink)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div className="label" style={{ padding: '14px 18px 8px' }}>SPACES IN THIS AREA</div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {mapList.map((item, i) => (
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
                        ${item.price}<span style={{ fontSize: 11, color: 'var(--label)' }}>{item.priceUnit}</span>
                      </span>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--label)', marginTop: 5 }}>
                      {item.typeLabel} · {item.size} · {item.dist}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, border: '1.5px solid var(--ink)', borderRadius: 6, padding: '2px 9px' }}>
                        {item.priceTypeLabel}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--muted-2)' }}>★ {item.rating}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* map canvas */}
          <div className="map-grid" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
            {/* faux streets */}
            <div style={{ position: 'absolute', left: 0, right: 0, top: '33%', height: 14, background: 'var(--tint)', borderTop: '1.5px solid #d2d3ca', borderBottom: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', left: 0, right: 0, top: '68%', height: 10, background: 'var(--tint)', borderTop: '1.5px solid #d2d3ca', borderBottom: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '43%', width: 14, background: 'var(--tint)', borderLeft: '1.5px solid #d2d3ca', borderRight: '1.5px solid #d2d3ca' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '78%', width: 10, background: 'var(--tint)', borderLeft: '1.5px solid #d2d3ca', borderRight: '1.5px solid #d2d3ca' }} />
            {/* green block */}
            <div style={{ position: 'absolute', left: '6%', top: '74%', width: 90, height: 60, background: '#dfe7d4', border: '1.5px solid #cdd6bf', borderRadius: 6 }} />

            {/* cluster bubble */}
            <div style={{ position: 'absolute', left: '86%', top: '20%', transform: 'translate(-50%,-50%)' }}>
              <div className="display" style={{ width: 50, height: 50, borderRadius: '50%', background: 'var(--ink)', color: '#fff', display: 'grid', placeItems: 'center', fontSize: 18, border: '2px solid #fff', boxShadow: '0 2px 6px rgba(0,0,0,.2)' }}>
                24
              </div>
            </div>

            {/* price-pill markers */}
            {mapPins.map((pin, i) => {
              const isSel = i === selected;
              return (
                <div
                  key={i}
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

            {/* selected callout card */}
            <SelectedCallout pin={mapPins[selected]} item={mapList[selected % mapList.length]} />

            {/* search this area */}
            {searchVisible && (
              <button
                onClick={() => setSearchVisible(false)}
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

            {/* approx-location chip */}
            <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', alignItems: 'center', gap: 7, background: '#fff', border: '1.5px solid var(--ink)', borderRadius: 9, padding: '7px 11px' }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', border: '2px solid var(--rust)' }} />
              <span className="mono" style={{ fontSize: 11, color: 'var(--muted-2)' }}>
                Approximate locations · exact address after booking
              </span>
            </div>

            {/* zoom controls */}
            <div style={{ position: 'absolute', bottom: 16, right: 16, display: 'flex', flexDirection: 'column', border: '1.5px solid var(--ink)', borderRadius: 9, overflow: 'hidden', background: '#fff' }}>
              <span className="clickable" style={{ padding: '8px 12px', fontSize: 18, textAlign: 'center', borderBottom: '1.5px solid var(--ink)' }}>+</span>
              <span className="clickable" style={{ padding: '8px 12px', fontSize: 18, textAlign: 'center' }}>−</span>
            </div>
          </div>
        </div>

        {showNotes && (
          <div style={{ padding: '14px 24px', borderTop: '1.5px solid var(--line-2)' }}>
            <Annotation>
              Pan/zoom does NOT refetch — once the view drifts past a threshold the "Search this area" button appears; tapping it queries GET /spaces/map?bbox=w,s,e,n. Markers use fuzzed coords; pins cap at ~200–300 with the true total shown separately; nearby pins cluster into count bubbles at low zoom.
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
          {item.typeLabel} · {item.size} · ★ {item.rating}
        </div>
      </div>
    </div>
  );
}
