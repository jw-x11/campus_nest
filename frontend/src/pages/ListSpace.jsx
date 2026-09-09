import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Field, Annotation } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { formPriceTypes } from '../data.js';
import { createSpace } from '../api.js';

function ChipGroup({ options, value, onChange, getKey = (o) => o, getLabel = (o) => o }) {
  return (
    <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
      {options.map((o) => {
        const key = getKey(o);
        return (
          <button
            key={key}
            type="button"
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
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [price, setPrice] = useState('');
  const [priceType, setPriceType] = useState('recurring_per_month');
  const [availableFrom, setAvailableFrom] = useState('');
  const [availableTo, setAvailableTo] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [createdId, setCreatedId] = useState(null);

  const publish = async () => {
    setError('');
    if (!title.trim() || !address.trim() || !city.trim() || !postalCode.trim() || !availableFrom || !availableTo) {
      setError('Title, address, city, postal code, and dates are required.');
      return;
    }
    if (availableTo < availableFrom) {
      setError('Available-to must be on or after available-from.');
      return;
    }
    setBusy(true);
    try {
      const space = await createSpace({
        title: title.trim(),
        description: description.trim() || null,
        address: address.trim(),
        city: city.trim(),
        postal_code: postalCode.trim(),
        price: Number(price) || 0,
        price_type: priceType,
        available_from: availableFrom,
        available_to: availableTo,
      });
      setCreatedId(space.id);
    } catch (err) {
      setError(err.message || 'Could not publish listing');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to="/" style={{ fontSize: 13.5, color: 'var(--muted)' }}>Cancel</Link>
        </div>

        <div style={{ padding: '34px 56px 16px', maxWidth: 820 }}>
          <h1 className="display" style={{ fontSize: 30 }}>List your space</h1>
          <div style={{ fontSize: 14.5, color: 'var(--muted)', marginTop: 6 }}>
            One form, one spaces row. You can edit or pause it anytime.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 28 }}>
            <Field label="LISTING TITLE">
              <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Walk-in closet near campus" />
            </Field>

            <Field label="DESCRIPTION">
              <textarea
                className="field"
                placeholder="Secure, dry, lockable closet a short walk from campus…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>

            <Field label="STREET ADDRESS" note="· private until booking">
              <input className="field" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="1842 Euclid Ave, Apt 3" />
            </Field>

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: '2 1 200px' }}>
                <Field label="CITY">
                  <input className="field" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Berkeley" />
                </Field>
              </div>
              <div style={{ flex: '1 1 110px' }}>
                <Field label="POSTAL CODE">
                  <input className="field" value={postalCode} onChange={(e) => setPostalCode(e.target.value)} placeholder="94709" />
                </Field>
              </div>
            </div>

            {showNotes && (
              <Annotation>
                latitude / longitude are optional on create. Exact address stays off public cards.
              </Annotation>
            )}

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 160px' }}>
                <Field label="PRICE · USD">
                  <div className="field">
                    <span style={{ color: 'var(--label)' }}>$</span>
                    <input
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      placeholder="45.00"
                      style={{ border: 'none', outline: 'none', width: '100%', background: 'transparent' }}
                    />
                  </div>
                </Field>
              </div>
              <div style={{ flex: '1.4 1 220px' }}>
                <Field label="PRICE TYPE">
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

            <Field label="AVAILABLE FROM → TO">
              <div className="field" style={{ gap: 10 }}>
                <input type="date" value={availableFrom} onChange={(e) => setAvailableFrom(e.target.value)} style={{ border: 'none', background: 'transparent' }} />
                <span style={{ color: '#bbb' }}>→</span>
                <input type="date" value={availableTo} onChange={(e) => setAvailableTo(e.target.value)} style={{ border: 'none', background: 'transparent' }} />
              </div>
            </Field>
          </div>
        </div>

        <div
          style={{
            position: 'sticky',
            bottom: 0,
            borderTop: '2px solid var(--ink)',
            background: '#fff',
            padding: '16px 56px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: createdId || error ? 'space-between' : 'flex-end',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          {error && (
            <span className="mono" style={{ fontSize: 13, color: 'var(--rust)' }}>{error}</span>
          )}
          {createdId && (
            <span className="mono" style={{ fontSize: 13, color: 'var(--rust)' }}>
              ✓ Listing published.
            </span>
          )}
          <div style={{ display: 'flex', gap: 10 }}>
            <Link to="/" className="btn">Cancel</Link>
            {createdId ? (
              <button className="btn btn-primary" onClick={() => navigate(`/space/${createdId}`)}>
                View listing →
              </button>
            ) : (
              <button className="btn btn-primary" onClick={publish} disabled={busy}>
                {busy ? 'Publishing…' : 'Publish listing'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
