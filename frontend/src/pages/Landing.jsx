import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext.jsx';
import { SearchIcon } from '../components/icons.jsx';
import { BodyLines, Annotation } from '../components/ui.jsx';
import { SpaceCard } from '../components/cards.jsx';
import Footer from '../components/Footer.jsx';
import {
  listings,
  valueProps,
  stepsRenter,
  stepsLister,
  spaceTypes,
} from '../data.js';

function PersonaToggle() {
  const { persona, setPersona } = useApp();
  return (
    <div
      style={{
        display: 'inline-flex',
        border: '2px solid var(--ink)',
        borderRadius: 999,
        padding: 3,
        background: '#fff',
      }}
    >
      {[
        ['renter', 'I need storage'],
        ['lister', 'I have space'],
      ].map(([key, label]) => (
        <button
          key={key}
          onClick={() => setPersona(key)}
          style={{
            cursor: 'pointer',
            border: 'none',
            fontSize: 14,
            padding: '7px 16px',
            borderRadius: 999,
            background: persona === key ? 'var(--accent)' : 'transparent',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function RenterHero() {
  const navigate = useNavigate();
  return (
    <div style={{ padding: '40px 56px 36px' }}>
      <span className="pill" style={{ color: 'var(--muted-2)', marginBottom: 20 }}>
        ● BERKELEY PILOT · SUMMER 2026
      </span>
      <h1 className="display" style={{ fontSize: 56, lineHeight: 0.95, maxWidth: '13ch', marginTop: 16 }}>
        Cheap storage, right next to campus.
      </h1>
      <div style={{ marginTop: 18, maxWidth: 540 }}>
        <BodyLines widths={['100%', '88%', '62%']} height={11} gap={8} />
      </div>
      <div
        className="clickable"
        onClick={() => navigate('/search')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          border: '2px solid var(--ink)',
          borderRadius: 14,
          padding: '9px 9px 9px 18px',
          marginTop: 30,
          maxWidth: 620,
        }}
      >
        <SearchIcon size={18} />
        <div style={{ flex: 1 }}>
          <div className="mono" style={{ fontSize: 11, color: 'var(--label)', letterSpacing: '.03em' }}>
            WHERE · WHEN · SIZE
          </div>
          <div style={{ fontSize: 15 }}>Berkeley · Jun 1 – Aug 20 · any size</div>
        </div>
        <span className="btn btn-primary">Search →</span>
      </div>
      <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginTop: 22, fontSize: 14, color: 'var(--muted-2)' }}>
        <span>★ 128 spaces in Berkeley</span>
        <span>◷ from $18/mo · no minimum</span>
      </div>
    </div>
  );
}

function ListerHero() {
  const navigate = useNavigate();
  return (
    <div style={{ padding: '40px 56px 36px' }}>
      <span className="pill" style={{ color: 'var(--muted-2)', marginBottom: 20 }}>
        ● FREE TO LIST · YOU APPROVE EVERY BOOKING
      </span>
      <h1 className="display" style={{ fontSize: 56, lineHeight: 0.95, maxWidth: '14ch', marginTop: 16 }}>
        Your empty closet could pay for textbooks.
      </h1>
      <div style={{ marginTop: 18, maxWidth: 540 }}>
        <BodyLines widths={['100%', '80%']} height={11} gap={8} />
      </div>
      <div style={{ border: '2px solid var(--ink)', borderRadius: 16, padding: 22, marginTop: 30, maxWidth: 560 }}>
        <div className="mono" style={{ fontSize: 12, color: 'var(--muted-2)', marginBottom: 14 }}>
          ESTIMATE YOUR EARNINGS
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 18 }}>
          {spaceTypes.slice(0, 5).map((label, i) => (
            <span
              key={label}
              style={{
                border: '1.5px solid var(--ink)',
                borderRadius: 9,
                padding: '7px 13px',
                fontSize: 13,
                background: i === 0 ? 'var(--accent)' : '#fff',
              }}
            >
              {label}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
          <div>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>A closet near campus earns about</div>
            <div className="display" style={{ fontSize: 48 }}>
              $45<span style={{ fontSize: 18, color: '#999' }}>/mo</span>
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => navigate('/list')}>
            List your space →
          </button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginTop: 22, fontSize: 14, color: 'var(--muted-2)' }}>
        <span>✓ Verified renters only</span>
        <span>✓ Set your own access rules</span>
        <span>✓ No commission in MVP</span>
      </div>
    </div>
  );
}

export default function Landing() {
  const { isRenter, showNotes } = useApp();
  const navigate = useNavigate();
  const steps = isRenter ? stepsRenter : stepsLister;
  const stepsTitle = isRenter ? 'Find space in three steps' : 'Start earning in three steps';

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* persona switch */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            padding: '18px 24px 0',
          }}
        >
          <PersonaToggle />
        </div>

        {isRenter ? <RenterHero /> : <ListerHero />}

        {showNotes && (
          <div style={{ padding: '0 56px 14px' }}>
            <Annotation>
              Persona toggle swaps the whole hero (renter search bar ⇄ lister earnings estimator).
            </Annotation>
          </div>
        )}

        {/* value strip */}
        <div
          style={{
            borderTop: '2px solid var(--ink)',
            borderBottom: '2px solid var(--ink)',
            background: 'var(--tint)',
            padding: '26px 56px',
            display: 'flex',
            gap: 22,
            flexWrap: 'wrap',
          }}
        >
          {valueProps.map((v) => (
            <div key={v.title} style={{ flex: '1 1 220px', display: 'flex', gap: 13, alignItems: 'flex-start' }}>
              <div
                className="mono"
                style={{
                  flex: 'none',
                  width: 38,
                  height: 38,
                  border: '1.5px solid var(--ink)',
                  borderRadius: 10,
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: 16,
                  background: 'var(--accent)',
                }}
              >
                {v.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16 }}>{v.title}</div>
                <div style={{ marginTop: 7 }}>
                  <BodyLines widths={['100%', '70%']} height={8} gap={5} />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* how it works */}
        <div style={{ padding: '42px 56px 10px' }}>
          <div className="label" style={{ letterSpacing: '.06em' }}>HOW IT WORKS</div>
          <div className="display" style={{ fontSize: 32, marginTop: 4 }}>{stepsTitle}</div>
          <div style={{ display: 'flex', gap: 20, marginTop: 24, flexWrap: 'wrap' }}>
            {steps.map((s) => (
              <div key={s.num} style={{ flex: '1 1 220px', border: '2px solid var(--ink)', borderRadius: 14, padding: 22 }}>
                <div
                  className="mono"
                  style={{
                    width: 34,
                    height: 34,
                    border: '1.5px solid var(--ink)',
                    borderRadius: 9,
                    display: 'grid',
                    placeItems: 'center',
                    fontSize: 14,
                    background: 'var(--accent)',
                  }}
                >
                  {s.num}
                </div>
                <div style={{ fontSize: 17, marginTop: 14 }}>{s.title}</div>
                <div style={{ marginTop: 9 }}>
                  <BodyLines widths={['100%', '100%', '55%']} height={8} gap={5} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* featured */}
        <div style={{ padding: '38px 56px 48px' }}>
          <div className="section-head" style={{ marginBottom: 20 }}>
            <div>
              <div className="label" style={{ letterSpacing: '.06em' }}>AVAILABLE NOW</div>
              <div className="display" style={{ fontSize: 32, marginTop: 4 }}>Spaces near campus</div>
            </div>
            <button className="chip" onClick={() => navigate('/search')}>
              See all 128 →
            </button>
          </div>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {listings.slice(0, 4).map((item) => (
              <div key={item.id} style={{ flex: '1 1 220px' }}>
                <SpaceCard item={item} />
              </div>
            ))}
          </div>
        </div>

        <Footer />
      </div>
    </div>
  );
}
