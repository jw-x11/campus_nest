import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Hatch, BodyLines, Avatar, Annotation } from '../components/ui.jsx';
import { SaveHeart } from '../components/cards.jsx';
import { useApp } from '../context/AppContext.jsx';
import { getListing, detailReviews } from '../data.js';

const PHOTO_COUNT = 5;

export default function SpaceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showNotes } = useApp();
  const item = getListing(id);
  const [photo, setPhoto] = useState(0);

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* breadcrumb */}
        <div style={{ padding: '13px 24px', borderBottom: '1.5px solid var(--line)', fontSize: 13, color: 'var(--muted)' }}>
          <Link to="/search">← Back to results</Link> &nbsp;·&nbsp; Berkeley &nbsp;›&nbsp; {item.typeLabel}
        </div>

        {/* gallery */}
        <div style={{ padding: '18px 24px' }}>
          <Hatch
            style={{
              position: 'relative',
              aspectRatio: 1.9,
              border: '1.5px solid var(--ink)',
              borderRadius: 12,
            }}
          >
            <span
              className="mono tag"
              style={{ position: 'absolute', top: 14, left: 14, background: 'var(--tint)' }}
            >
              PHOTO {photo + 1} / {PHOTO_COUNT}
            </span>
            <GalleryArrow side="left" onClick={() => setPhoto((p) => (p - 1 + PHOTO_COUNT) % PHOTO_COUNT)} />
            <GalleryArrow side="right" onClick={() => setPhoto((p) => (p + 1) % PHOTO_COUNT)} />
            <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 8 }}>
              {Array.from({ length: PHOTO_COUNT }).map((_, i) => (
                <span
                  key={i}
                  onClick={() => setPhoto(i)}
                  className="clickable"
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: '50%',
                    background: i === photo ? 'var(--ink)' : 'transparent',
                    border: '1.5px solid var(--ink)',
                  }}
                />
              ))}
            </div>
          </Hatch>
        </div>

        {/* body */}
        <div style={{ display: 'flex', alignItems: 'flex-start', borderTop: '1.5px solid var(--line)', flexWrap: 'wrap' }}>
          {/* main */}
          <div style={{ flex: '1 1 520px', minWidth: 0, padding: '26px 28px 36px', borderRight: '2px solid var(--ink)' }}>
            <span className="tag">{item.typeLabel.toUpperCase()}</span>
            <h1 className="display" style={{ fontSize: 32, marginTop: 12 }}>{item.title}</h1>
            <div style={{ fontSize: 14.5, color: 'var(--muted-2)', marginTop: 7 }}>
              ★ {item.rating} ({item.reviews} reviews) · {item.dist} from campus
            </div>

            {/* key facts */}
            <div style={{ display: 'flex', border: '1.5px solid var(--ink)', borderRadius: 12, marginTop: 22, overflow: 'hidden' }}>
              {[
                ['TYPE', item.typeLabel],
                ['PRICE', `$${item.price} ${item.priceUnit}`],
                ['AVAILABLE', 'Jun 1 – Aug 20'],
              ].map(([k, v], i) => (
                <div key={k} style={{ flex: 1, padding: 16, borderRight: i < 2 ? '1.5px solid var(--line)' : 'none' }}>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--label)' }}>{k}</div>
                  <div style={{ fontSize: 15, marginTop: 5 }}>{v}</div>
                </div>
              ))}
            </div>

            <Section title="About this space">
              <BodyLines widths={['100%', '97%', '88%', '54%']} height={9} gap={8} />
            </Section>

            <Section title="Approximate location">
              <div
                className="mini-map"
                style={{
                  height: 150,
                  border: '1.5px solid var(--ink)',
                  borderRadius: 12,
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                <span
                  style={{
                    width: 64,
                    height: 64,
                    border: '2px dashed var(--ink)',
                    borderRadius: 999,
                    background: 'rgba(189,86,56,.12)',
                  }}
                />
              </div>
              {showNotes && (
                <Annotation style={{ marginTop: 10 }}>
                  Only a fuzzed ~block-level circle shows. Exact address is revealed after the host confirms the booking.
                </Annotation>
              )}
            </Section>

            <Section title={`★ ${item.rating} · ${item.reviews} reviews`}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {detailReviews.map((r) => (
                  <div key={r.initials} style={{ border: '1.5px solid var(--line)', borderRadius: 12, padding: 15 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Avatar size={32}>{r.initials}</Avatar>
                      <div>
                        <div style={{ fontSize: 14 }}>{r.name}</div>
                        <div className="mono" style={{ fontSize: 11, color: 'var(--label)' }}>{r.when}</div>
                      </div>
                      <span style={{ marginLeft: 'auto', fontSize: 13 }}>{r.rating}</span>
                    </div>
                    <div style={{ marginTop: 11 }}>
                      <BodyLines widths={['100%', '62%']} height={8} gap={7} />
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          {/* booking sidebar */}
          <div style={{ flex: '0 0 312px', width: 312, padding: 24 }}>
            <div style={{ border: '2px solid var(--ink)', borderRadius: 14, padding: 20, position: 'sticky', top: 90 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span className="display" style={{ fontSize: 34 }}>${item.price}</span>
                <span style={{ fontSize: 14, color: 'var(--label)' }}>{item.priceUnit === '/wk' ? '/week' : '/month'}</span>
              </div>

              <div style={{ display: 'flex', border: '1.5px solid var(--ink)', borderRadius: 11, marginTop: 16, overflow: 'hidden' }}>
                {[['START', 'Jun 1'], ['END', 'Aug 20']].map(([k, v], i) => (
                  <div key={k} style={{ flex: 1, padding: '11px 13px', borderRight: i === 0 ? '1.5px solid var(--ink)' : 'none' }}>
                    <div className="mono" style={{ fontSize: 9.5, color: 'var(--label)' }}>{k}</div>
                    <div style={{ fontSize: 13.5, marginTop: 3 }}>{v}</div>
                  </div>
                ))}
              </div>

              <div style={{ border: '1.5px solid var(--ink)', borderRadius: 11, marginTop: 10, padding: '11px 13px' }}>
                <div className="mono" style={{ fontSize: 9.5, color: 'var(--label)' }}>MESSAGE TO HOST</div>
                <textarea
                  className="field"
                  placeholder="Hi! I'd love to book this space…"
                  style={{ border: 'none', padding: '7px 0 0', minHeight: 44, fontSize: 13.5, boxShadow: 'none' }}
                />
              </div>

              <button
                className="btn btn-primary btn-block"
                style={{ marginTop: 14 }}
                onClick={() => navigate(`/book/${item.id}`)}
              >
                Request to book
              </button>
              <div style={{ display: 'flex', gap: 8, marginTop: 9 }}>
                <span className="chip" style={{ flex: 1, justifyContent: 'center', gap: 6 }}>
                  <SaveHeart id={item.id} round={false} /> Save
                </span>
                <Link to="/messages" className="chip" style={{ flex: 1, justifyContent: 'center' }}>
                  Message
                </Link>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', marginTop: 12, lineHeight: 1.4 }}>
                You won't be charged yet. Host approves within 24h.
              </div>

              <Link
                to="/profile/sam-k"
                style={{ borderTop: '1.5px solid var(--line)', marginTop: 18, paddingTop: 16, display: 'flex', alignItems: 'center', gap: 11 }}
              >
                <Avatar size={42}>SK</Avatar>
                <div>
                  <div style={{ fontSize: 14.5 }}>Hosted by Sam K.</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--label)' }}>★ 4.9 · UC Berkeley · since 2025</div>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginTop: 26 }}>
      <div className="display" style={{ fontSize: 19, marginBottom: 11 }}>{title}</div>
      {children}
    </div>
  );
}

function GalleryArrow({ side, onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label={side === 'left' ? 'Previous photo' : 'Next photo'}
      style={{
        position: 'absolute',
        top: '50%',
        [side]: 16,
        transform: 'translateY(-50%)',
        width: 42,
        height: 42,
        border: '1.5px solid var(--ink)',
        borderRadius: '50%',
        background: 'var(--tint)',
        display: 'grid',
        placeItems: 'center',
        fontSize: 18,
        cursor: 'pointer',
      }}
    >
      {side === 'left' ? '‹' : '›'}
    </button>
  );
}
