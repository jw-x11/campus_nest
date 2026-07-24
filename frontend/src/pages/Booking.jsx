import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Hatch, Field, Annotation } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { getListing } from '../data.js';

export default function Booking() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showNotes } = useApp();
  const item = getListing(id);
  const [sent, setSent] = useState(false);

  // 2 mo 19 days → billed as 3 months (rounded up) for the demo window.
  const months = 3;
  const total = item.price * months;

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* sub nav */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to={`/space/${item.id}`} style={{ fontSize: 13.5, color: 'var(--muted)' }}>← Back to listing</Link>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {/* left: details */}
          <div style={{ flex: '1 1 460px', minWidth: 0, padding: '34px 40px 40px', borderRight: '2px solid var(--ink)' }}>
            <h1 className="display" style={{ fontSize: 28 }}>Request to book</h1>
            <div style={{ fontSize: 14.5, color: 'var(--muted)', marginTop: 6 }}>
              Creates a <code className="mono" style={{ fontSize: 12.5, color: 'var(--muted-3)' }}>bookings</code> row with status{' '}
              <code className="mono" style={{ fontSize: 12.5, color: 'var(--muted-3)' }}>pending</code> until the host approves.
            </div>

            {/* space summary */}
            <div style={{ marginTop: 26, display: 'flex', alignItems: 'center', gap: 16, border: '1.5px solid var(--ink)', borderRadius: 12, padding: 16 }}>
              <Hatch style={{ flex: 'none', width: 88, height: 88, border: '1.5px solid var(--ink)', borderRadius: 11 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 17 }}>{item.title}</div>
                <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 5 }}>
                  {item.typeLabel} · {item.size} · {item.dist} · Berkeley
                </div>
                <div className="field-key" style={{ marginTop: 6 }}>bookings.space_id → spaces.id</div>
              </div>
              <div style={{ textAlign: 'right', flex: 'none' }}>
                <div className="display" style={{ fontSize: 22, lineHeight: 1 }}>
                  ${item.price}<span style={{ fontSize: 14, color: 'var(--label)' }}>{item.priceUnit}</span>
                </div>
              </div>
            </div>

            {/* dates */}
            <div style={{ marginTop: 24, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 180px' }}>
                <Field label="START DATE" fieldKey="bookings.start_date">
                  <input type="date" className="field" defaultValue="2026-06-01" />
                </Field>
              </div>
              <div style={{ flex: '1 1 180px' }}>
                <Field label="END DATE" fieldKey="bookings.end_date">
                  <input type="date" className="field" defaultValue="2026-08-20" />
                </Field>
              </div>
            </div>
            <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 9 }}>
              2 mo 19 days → billed as 3 months (rounded up) · within available window (Jun 1 – Aug 20)
            </div>

            {/* message to host */}
            <div style={{ marginTop: 24 }}>
              <Field label="MESSAGE TO HOST" fieldKey="opens a conversation thread">
                <textarea className="field" placeholder="Hi! I'd like to store about 8 boxes and a bike…" />
              </Field>
            </div>
          </div>

          {/* right: summary */}
          <div style={{ flex: '0 0 380px', width: 380, padding: '34px 32px 40px', background: 'var(--tint-2)' }}>
            <div className="label" style={{ marginBottom: 16 }}>BOOKING SUMMARY</div>

            <Row label="Rate" value={`$${item.price.toFixed(2)} ${item.priceUnit}`} />
            <Row label="Duration" value={<span>{months} mo <span style={{ color: 'var(--label)', fontSize: 12.5 }}>(rounded up)</span></span>} />

            <div style={{ borderTop: '1.5px solid #d6d6cf', paddingTop: 16, marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>Est. total</div>
                <div className="field-key" style={{ marginTop: 3 }}>arranged directly with host</div>
              </div>
              <div className="display" style={{ fontSize: 26 }}>${total}</div>
            </div>

            <div style={{ marginTop: 20, background: 'var(--hatch-bg)', borderRadius: 11, padding: '13px 14px', fontSize: 13, color: 'var(--muted-2)', lineHeight: 1.5 }}>
              Pay the host directly (Venmo, Zelle, cash) — campus nest doesn't process payments in the pilot.
            </div>

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
                  bookings row created · status=pending
                </div>
                <Link to="/messages" className="btn btn-primary btn-block" style={{ marginTop: 12 }}>
                  Go to messages →
                </Link>
              </div>
            ) : (
              <button className="btn btn-primary btn-block" style={{ marginTop: 18, fontWeight: 600 }} onClick={() => setSent(true)}>
                Send booking request
              </button>
            )}
            <div className="mono" style={{ fontSize: 11, color: 'var(--label)', textAlign: 'center', marginTop: 11, lineHeight: 1.5 }}>
              Host approves within 24h, then you settle up directly.
            </div>

            {showNotes && (
              <Annotation style={{ marginTop: 18 }}>
                Submitting inserts a bookings row (status=pending). No payments table in the MVP — renters pay hosts directly. Exact address revealed only after status=confirmed.
              </Annotation>
            )}
          </div>
        </div>
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
