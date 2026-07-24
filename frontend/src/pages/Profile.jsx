import { Link } from 'react-router-dom';
import { Hatch, BodyLines, Avatar, Annotation } from '../components/ui.jsx';
import { SpaceCard } from '../components/cards.jsx';
import { useApp } from '../context/AppContext.jsx';
import { profile, listings } from '../data.js';

export default function Profile() {
  const { showNotes } = useApp();
  const profileListings = listings.slice(0, 3);

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        {/* sub nav */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to="/search" style={{ fontSize: 13.5, color: 'var(--muted)' }}>← Back</Link>
        </div>

        <div style={{ display: 'flex', alignItems: 'stretch', flexWrap: 'wrap' }}>
          {/* identity card */}
          <div style={{ flex: '0 0 360px', width: 360, borderRight: '2px solid var(--ink)', padding: '34px 30px 36px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
              <Hatch style={{ width: 118, height: 118, border: '2px solid var(--ink)', borderRadius: '50%' }} />
              <div className="display" style={{ fontSize: 26, marginTop: 16 }}>{profile.name}</div>
              <div style={{ fontSize: 14, color: 'var(--muted)', marginTop: 4 }}>{profile.school}</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 8 }}>{profile.memberSince}</div>
            </div>

            {/* stats */}
            <div style={{ display: 'flex', justifyContent: 'space-between', border: '1.5px solid var(--ink)', borderRadius: 13, padding: '16px 6px', marginTop: 24 }}>
              {profile.stats.map((s) => (
                <div key={s.label} style={{ flex: 1, textAlign: 'center' }}>
                  <div className="display" style={{ fontSize: 24 }}>{s.num}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--label)', marginTop: 7, lineHeight: 1.2 }}>{s.label}</div>
                </div>
              ))}
            </div>

            {/* actions */}
            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Link to="/messages" className="btn btn-primary" style={{ fontWeight: 600 }}>Message {profile.name.split(' ')[0]}</Link>
              <Link to="/search" className="btn">View all listings</Link>
            </div>

            {/* contact rows */}
            <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 13 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="label" style={{ minWidth: 74 }}>UNIVERSITY</span>
                <span style={{ fontSize: 14 }}>{profile.university}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="label" style={{ minWidth: 74 }}>VERIFIED</span>
                <span className="tag" style={{ borderColor: 'var(--rust)', color: 'var(--rust)' }}>✓ .edu email</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="label" style={{ minWidth: 74 }}>PHONE</span>
                <span className="mono" style={{ fontSize: 12.5, color: 'var(--label)' }}>private until booking</span>
              </div>
            </div>
          </div>

          {/* right: bio + listings + reviews */}
          <div style={{ flex: '1 1 480px', minWidth: 0, padding: '34px 40px 40px' }}>
            <div className="label" style={{ marginBottom: 10 }}>ABOUT</div>
            <div style={{ fontSize: 15.5, color: '#444', lineHeight: 1.6, maxWidth: '60ch' }}>{profile.bio}</div>

            <div className="label" style={{ margin: '30px 0 14px' }}>LISTINGS · 3 ACTIVE</div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {profileListings.map((item) => (
                <div key={item.id} style={{ flex: '1 1 180px' }}>
                  <SpaceCard item={item} showHeart={false} />
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '30px 0 4px' }}>
              <span className="label">REVIEWS</span>
              <span style={{ fontSize: 13.5 }}>★ 4.9 · 47 reviews</span>
            </div>
            <div>
              {profile.reviews.map((r) => (
                <div key={r.initials} style={{ display: 'flex', gap: 13, padding: '16px 0', borderTop: '1.5px solid var(--line-2)' }}>
                  <Avatar size={42} style={{ background: 'var(--tint)' }}>{r.initials}</Avatar>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
                      <span style={{ fontSize: 14.5 }}>
                        {r.name} <span className="mono" style={{ fontSize: 10.5, color: 'var(--label)' }}>· {r.role}</span>
                      </span>
                      <span className="mono" style={{ fontSize: 11.5, color: 'var(--label)', whiteSpace: 'nowrap' }}>{r.when}</span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--rust)', marginTop: 4 }}>{r.rating}</div>
                    <div style={{ marginTop: 9 }}>
                      <BodyLines widths={['100%', '68%']} height={8} gap={6} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {showNotes && (
          <div style={{ padding: '14px 24px', borderTop: '1.5px solid var(--line-2)' }}>
            <Annotation>
              Public profile shows display name, university, bio, member-since, active listings, and aggregated reviews. Phone stays private until a booking is confirmed. Reviews render in both directions (renter→lister, lister→renter).
            </Annotation>
          </div>
        )}
      </div>
    </div>
  );
}
