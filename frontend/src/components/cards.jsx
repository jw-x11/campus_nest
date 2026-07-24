import { useNavigate } from 'react-router-dom';
import { Hatch } from './ui.jsx';
import { HeartIcon } from './icons.jsx';
import { useApp } from '../context/AppContext.jsx';

function SaveHeart({ id, round = true }) {
  const { isSaved, toggleSaved } = useApp();
  const saved = isSaved(id);
  return (
    <button
      aria-label={saved ? 'Remove from saved' : 'Save'}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleSaved(id);
      }}
      style={{
        width: 28,
        height: 28,
        background: saved ? 'var(--accent)' : '#fff',
        border: '1.5px solid var(--ink)',
        borderRadius: round ? 999 : 8,
        display: 'grid',
        placeItems: 'center',
        cursor: 'pointer',
        flex: 'none',
      }}
    >
      <HeartIcon size={14} filled={saved} />
    </button>
  );
}

// Vertical card — landing "featured", profile listings, saved grid thumbnails.
export function SpaceCard({ item, showHeart = true }) {
  const navigate = useNavigate();
  return (
    <div
      className="wire-card clickable"
      style={{ flex: 1, borderRadius: 14, boxShadow: 'none', minWidth: 0 }}
      onClick={() => navigate(`/space/${item.id}`)}
    >
      <Hatch
        style={{
          position: 'relative',
          aspectRatio: 1.4,
          borderBottom: '1.5px solid var(--ink)',
        }}
      >
        <span className="tag" style={{ position: 'absolute', top: 10, left: 10 }}>
          {item.typeLabel}
        </span>
        {showHeart && (
          <div style={{ position: 'absolute', top: 9, right: 9 }}>
            <SaveHeart id={item.id} />
          </div>
        )}
      </Hatch>
      <div style={{ padding: '13px 15px 16px' }}>
        <div style={{ fontSize: 15 }}>{item.title}</div>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 5 }}>
          {item.size} · {item.dist} from campus
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            marginTop: 11,
          }}
        >
          <span className="display" style={{ fontSize: 22 }}>
            ${item.price}
            <span style={{ fontSize: 12, color: 'var(--label)' }}>{item.priceUnit}</span>
          </span>
          <span style={{ fontSize: 13, color: 'var(--muted-2)' }}>★ {item.rating}</span>
        </div>
      </div>
    </div>
  );
}

// Horizontal row — search results list.
export function ResultRow({ item }) {
  const navigate = useNavigate();
  return (
    <div
      className="clickable"
      onClick={() => navigate(`/space/${item.id}`)}
      style={{
        display: 'flex',
        gap: 16,
        alignItems: 'center',
        padding: '16px 22px',
        borderBottom: '1.5px solid var(--line)',
      }}
    >
      <Hatch
        style={{
          flex: 'none',
          width: 84,
          height: 84,
          border: '1.5px solid var(--ink)',
          borderRadius: 11,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 15.5, display: 'flex', alignItems: 'center', gap: 8 }}>
          {item.title}
          {item.verified && (
            <span className="tag" style={{ borderColor: 'var(--rust)', color: 'var(--rust)' }}>
              ✓ verified
            </span>
          )}
        </div>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 5 }}>
          {item.typeLabel} · {item.size} · {item.dist} · {item.accessLabel}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 9, flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              border: '1.5px solid var(--ink)',
              borderRadius: 7,
              padding: '3px 11px',
            }}
          >
            {item.priceTypeLabel}
          </span>
          {item.amenities.map((am) => (
            <span
              key={am}
              style={{
                fontSize: 11.5,
                color: 'var(--muted-2)',
                border: '1.5px solid #d6d6cf',
                borderRadius: 6,
                padding: '2px 9px',
              }}
            >
              {am}
            </span>
          ))}
        </div>
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: 10,
          flex: 'none',
        }}
      >
        <div style={{ textAlign: 'right' }}>
          <div className="display" style={{ fontSize: 22, lineHeight: 1 }}>
            ${item.price}
            <span style={{ fontSize: 14, color: 'var(--label)' }}>{item.priceUnit}</span>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--muted-2)', marginTop: 4 }}>
            ★ {item.rating} ({item.reviews})
          </div>
        </div>
        <div
          className="chip btn-sm"
          onClick={(e) => e.stopPropagation()}
          style={{ gap: 6 }}
        >
          <SaveHeart id={item.id} round={false} /> Save
        </div>
      </div>
    </div>
  );
}

export { SaveHeart };
