import { useState } from 'react';
import { useApp } from '../context/AppContext.jsx';

// Floating panel mirroring the wireframe's persona / annotation "tweaks".
export default function Controls() {
  const { persona, setPersona, showNotes, toggleNotes } = useApp();
  const [open, setOpen] = useState(false);

  return (
    <div style={{ position: 'fixed', right: 18, bottom: 18, zIndex: 100 }}>
      {open && (
        <div
          className="wire-card"
          style={{ width: 232, padding: 16, marginBottom: 10, borderRadius: 14 }}
        >
          <div className="label" style={{ marginBottom: 12 }}>
            Prototype tweaks
          </div>

          <div className="label" style={{ fontSize: 10, marginBottom: 7 }}>
            Persona
          </div>
          <div
            style={{
              display: 'flex',
              border: '2px solid var(--ink)',
              borderRadius: 999,
              padding: 3,
              marginBottom: 16,
            }}
          >
            {['renter', 'lister'].map((p) => (
              <button
                key={p}
                onClick={() => setPersona(p)}
                style={{
                  flex: 1,
                  cursor: 'pointer',
                  border: 'none',
                  borderRadius: 999,
                  padding: '7px 0',
                  fontSize: 13,
                  textTransform: 'capitalize',
                  background: persona === p ? 'var(--accent)' : 'transparent',
                }}
              >
                {p}
              </button>
            ))}
          </div>

          <label
            className="clickable"
            style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14 }}
          >
            <span
              onClick={toggleNotes}
              style={{
                width: 18,
                height: 18,
                border: '1.5px solid var(--ink)',
                borderRadius: 5,
                display: 'grid',
                placeItems: 'center',
                background: showNotes ? 'var(--accent)' : '#fff',
              }}
            >
              {showNotes ? '✓' : ''}
            </span>
            Show annotations
          </label>
        </div>
      )}

      <button
        className="btn btn-primary"
        onClick={() => setOpen((o) => !o)}
        style={{ borderRadius: 999, boxShadow: 'var(--shadow-sm)' }}
      >
        {open ? '✕ Close' : '✎ Tweaks'}
      </button>
    </div>
  );
}
