import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Field, Annotation } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { spaceTypes, formPriceTypes } from '../data.js';

function ChipGroup({ options, value, onChange, getKey = (o) => o, getLabel = (o) => o }) {
  return (
    <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
      {options.map((o) => {
        const key = getKey(o);
        return (
          <button
            key={key}
            onClick={() => onChange(key)}
            style={{
              border: '1.5px solid var(--ink)',
              borderRadius: 10,
              padding: '9px 16px',
              fontSize: 14,
              cursor: 'pointer',
              background: value === key ? 'var(--accent)' : '#fff',
            }}
          >
            {getLabel(o)}
          </button>
        );
      })}
    </div>
  );
}

export default function ListSpace() {
  const { showNotes } = useApp();
  const navigate = useNavigate();
  const [type, setType] = useState('Closet');
  const [priceType, setPriceType] = useState('recurring_per_month');
  const [published, setPublished] = useState(false);

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* sub nav */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to="/" style={{ fontSize: 13.5, color: 'var(--muted)' }}>Cancel</Link>
        </div>

        <div style={{ padding: '34px 56px 16px', maxWidth: 820 }}>
          <h1 className="display" style={{ fontSize: 30 }}>List your space</h1>
          <div style={{ fontSize: 14.5, color: 'var(--muted)', marginTop: 6 }}>
            One form, one <code className="mono" style={{ fontSize: 12.5, color: 'var(--muted-3)' }}>spaces</code> row. You can edit or pause it anytime.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 28 }}>
            <Field label="LISTING TITLE" fieldKey="spaces.title">
              <input className="field" defaultValue="Walk-in closet, North Side" />
            </Field>

            <Field label="SPACE TYPE" fieldKey="spaces.type · enum">
              <ChipGroup options={spaceTypes} value={type} onChange={setType} />
            </Field>

            <Field label="DESCRIPTION" fieldKey="spaces.description · optional">
              <textarea
                className="field"
                placeholder="Secure, dry, lockable closet a short walk from North Gate…"
                defaultValue=""
              />
            </Field>

            <Field label="STREET ADDRESS" fieldKey="spaces.address" note="· private until booking">
              <input className="field" defaultValue="1842 Euclid Ave, Apt 3" />
            </Field>

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: '2 1 200px' }}>
                <Field label="CITY" fieldKey="spaces.city">
                  <input className="field" defaultValue="Berkeley" />
                </Field>
              </div>
              <div style={{ flex: '1 1 90px' }}>
                <Field label="STATE" fieldKey="spaces.state">
                  <input className="field" defaultValue="CA" />
                </Field>
              </div>
              <div style={{ flex: '1 1 110px' }}>
                <Field label="POSTAL CODE" fieldKey="spaces.postal_code">
                  <input className="field" defaultValue="94709" />
                </Field>
              </div>
            </div>

            {showNotes && (
              <Annotation>
                latitude / longitude are geocoded server-side from the address — never user-entered, never shown to renters before a booking is confirmed.
              </Annotation>
            )}

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 160px' }}>
                <Field label="PRICE · USD" fieldKey="spaces.price">
                  <div className="field">
                    <span style={{ color: 'var(--label)' }}>$</span>
                    <input
                      defaultValue="45.00"
                      style={{ border: 'none', outline: 'none', width: '100%', background: 'transparent' }}
                    />
                  </div>
                </Field>
              </div>
              <div style={{ flex: '1.4 1 220px' }}>
                <Field label="PRICE TYPE" fieldKey="spaces.price_type · enum">
                  <ChipGroup
                    options={formPriceTypes}
                    value={priceType}
                    onChange={setPriceType}
                    getKey={(o) => o.sub}
                    getLabel={(o) => o.label}
                  />
                </Field>
              </div>
            </div>

            <Field label="AVAILABLE FROM → TO" fieldKey="available_from / available_to">
              <div className="field" style={{ gap: 10 }}>
                <input type="date" defaultValue="2026-06-01" style={{ border: 'none', background: 'transparent' }} />
                <span style={{ color: '#bbb' }}>→</span>
                <input type="date" defaultValue="2026-08-20" style={{ border: 'none', background: 'transparent' }} />
              </div>
            </Field>

            <Field label="PHOTOS · UP TO 10" fieldKey="space_images">
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <div
                  style={{
                    width: 118,
                    height: 90,
                    border: '2px dashed var(--ink)',
                    borderRadius: 11,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 5,
                    color: 'var(--muted-2)',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ fontSize: 22, lineHeight: 1 }}>＋</span>
                  <span className="mono" style={{ fontSize: 10 }}>UPLOAD</span>
                </div>
                {[1, 2, 3].map((g) => (
                  <div
                    key={g}
                    className="hatch"
                    style={{ width: 118, height: 90, border: '1.5px solid var(--ink)', borderRadius: 11 }}
                  />
                ))}
              </div>
            </Field>
          </div>
        </div>

        {/* publish bar */}
        <div
          style={{
            position: 'sticky',
            bottom: 0,
            borderTop: '2px solid var(--ink)',
            background: '#fff',
            padding: '16px 56px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: published ? 'space-between' : 'flex-end',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          {published && (
            <span className="mono" style={{ fontSize: 13, color: 'var(--rust)' }}>
              ✓ Listing published — inserted a <b>spaces</b> row (status=active).
            </span>
          )}
          <div style={{ display: 'flex', gap: 10 }}>
            <Link to="/" className="btn">Cancel</Link>
            {published ? (
              <button className="btn btn-primary" onClick={() => navigate('/space/walkin-closet-north')}>
                View listing →
              </button>
            ) : (
              <button className="btn btn-primary" onClick={() => setPublished(true)}>
                Publish listing
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
