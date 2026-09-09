import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Hatch, Field, Annotation, PageStatus } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { createBooking, estimateTotal, formatPrice, getSpace } from '../api.js';

export default function Booking() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showNotes } = useApp();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getSpace(id)
      .then((space) => {
        if (cancelled) return;
        setItem(space);
        setStartDate(space.availableFrom || '');
        setEndDate(space.availableTo || '');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load listing');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const total = useMemo(
    () => (item ? estimateTotal(item.price, item.priceType, startDate, endDate) : 0),
    [item, startDate, endDate],
  );

  const submit = async () => {
    if (!item) return;
    setBusy(true);
    setError('');
    try {
      const booking = await createBooking({
        spaceId: item.id,
        startDate,
        endDate,
      });
      setSent(booking);
    } catch (err) {
      setError(err.message || 'Could not send booking request');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to={item ? `/space/${item.id}` : '/search'} style={{ fontSize: 13.5, color: 'var(--muted)' }}>
            ← Back to listing
          </Link>
        </div>

        {loading && <PageStatus>Loading listing…</PageStatus>}

        {item && (
          <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 460px', minWidth: 0, padding: '34px 40px 40px', borderRight: '2px solid var(--ink)' }}>
              <h1 className="display" style={{ fontSize: 28 }}>Request to book</h1>
              <div style={{ fontSize: 14.5, color: 'var(--muted)', marginTop: 6 }}>
                Creates a booking with status pending until the host approves.
              </div>

              <div style={{ marginTop: 26, display: 'flex', alignItems: 'center', gap: 16, border: '1.5px solid var(--ink)', borderRadius: 12, padding: 16 }}>
                <Hatch style={{ flex: 'none', width: 88, height: 88, border: '1.5px solid var(--ink)', borderRadius: 11 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 17 }}>{item.title}</div>
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 5 }}>
                    {item.city} · {item.priceTypeLabel}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flex: 'none' }}>
                  <div className="display" style={{ fontSize: 22, lineHeight: 1 }}>
                    ${formatPrice(item.price)}<span style={{ fontSize: 14, color: 'var(--label)' }}>{item.priceUnit}</span>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 24, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 180px' }}>
                  <Field label="START DATE">
                    <input
                      type="date"
                      className="field"
                      value={startDate}
                      min={item.availableFrom || undefined}
                      max={item.availableTo || undefined}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </Field>
                </div>
                <div style={{ flex: '1 1 180px' }}>
                  <Field label="END DATE">
                    <input
                      type="date"
                      className="field"
                      value={endDate}
                      min={startDate || item.availableFrom || undefined}
                      max={item.availableTo || undefined}
                      onChange={(e) => setEndDate(e.target.value)}
                    />
                  </Field>
                </div>
              </div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 9 }}>
                Dates must fall inside the listing window
                {item.availableFrom ? ` (${item.availableFrom} → ${item.availableTo})` : ''}.
              </div>
            </div>

            <div style={{ flex: '0 0 380px', width: 380, padding: '34px 32px 40px', background: 'var(--tint-2)' }}>
              <div className="label" style={{ marginBottom: 16 }}>BOOKING SUMMARY</div>

              <Row label="Rate" value={`$${formatPrice(item.price)} ${item.priceUnit}`} />
              <Row label="Window" value={`${startDate || '—'} → ${endDate || '—'}`} />

              <div style={{ borderTop: '1.5px solid #d6d6cf', paddingTop: 16, marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>Est. total</div>
                  <div className="field-key" style={{ marginTop: 3 }}>arranged directly with host</div>
                </div>
                <div className="display" style={{ fontSize: 26 }}>${formatPrice(sent?.total_price ?? total)}</div>
              </div>

              <div style={{ marginTop: 20, background: 'var(--hatch-bg)', borderRadius: 11, padding: '13px 14px', fontSize: 13, color: 'var(--muted-2)', lineHeight: 1.5 }}>
                Pay the host directly (Venmo, Zelle, cash) — campus nest doesn't process payments in the pilot.
              </div>

              {error && (
                <div style={{ marginTop: 14, fontSize: 14, color: 'var(--rust)' }}>{error}</div>
              )}

              {sent ? (
                <div
                  style={{
                    marginTop: 18,
                    border: '2px solid var(--ink)',
                    borderRadius: 11,
                    padding: 14,
                    textAlign: 'center',
                    fontSize: 14,
                    background: '#fff',
                  }}
                >
                  <div style={{ fontWeight: 600 }}>✓ Request sent</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--label)', marginTop: 6 }}>
                    status={sent.status || 'pending'}
                  </div>
                  <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} onClick={() => navigate('/messages')}>
                    Go to messages →
                  </button>
                </div>
              ) : (
                <button className="btn btn-primary btn-block" style={{ marginTop: 18, fontWeight: 600 }} onClick={submit} disabled={busy || !startDate || !endDate}>
                  {busy ? 'Sending…' : 'Send booking request'}
                </button>
              )}
              <div className="mono" style={{ fontSize: 11, color: 'var(--label)', textAlign: 'center', marginTop: 11, lineHeight: 1.5 }}>
                Host approves within 24h, then you settle up directly.
              </div>

              {showNotes && (
                <Annotation style={{ marginTop: 18 }}>
                  Submitting posts to POST /bookings. Exact address is revealed only after status=confirmed.
                </Annotation>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14.5, marginBottom: 12 }}>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
