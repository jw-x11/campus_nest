import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Hatch, Annotation, PageStatus } from '../components/ui.jsx';
import { SpaceCard } from '../components/cards.jsx';
import { useApp } from '../context/AppContext.jsx';
import { initials, listMySpaces, memberSince } from '../api.js';

export default function Profile() {
  const { showNotes, user, logout, saved } = useApp();
  const [listings, setListings] = useState([]);
  const [listingCount, setListingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    listMySpaces(1, 6)
      .then((data) => {
        if (cancelled) return;
        setListings(data.spaces);
        setListingCount(data.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load your listings');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = [
    { num: String(listingCount), label: 'Active listings' },
    { num: String(saved.size), label: 'Saved spaces' },
    { num: user?.isVerified ? 'Yes' : 'No', label: 'Verified' },
  ];

  return (
    <div className="page">
      <div className="wire-card" style={{ borderRadius: 5 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 24px', borderBottom: '1.5px solid var(--line)' }}>
          <Link to="/search" style={{ fontSize: 13.5, color: 'var(--muted)' }}>← Back</Link>
        </div>

        <div style={{ display: 'flex', alignItems: 'stretch', flexWrap: 'wrap' }}>
          <div style={{ flex: '0 0 360px', width: 360, borderRight: '2px solid var(--ink)', padding: '34px 30px 36px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
              {user?.avatarUrl ? (
                <img
                  src={user.avatarUrl}
                  alt=""
                  style={{ width: 118, height: 118, border: '2px solid var(--ink)', borderRadius: '50%', objectFit: 'cover' }}
                />
              ) : (
                <Hatch style={{ width: 118, height: 118, border: '2px solid var(--ink)', borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 28 }}>
                  {initials(user?.username)}
                </Hatch>
              )}
              <div className="display" style={{ fontSize: 26, marginTop: 16 }}>{user?.username}</div>
              <div style={{ fontSize: 14, color: 'var(--muted)', marginTop: 4 }}>{user?.university || user?.email}</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--label)', marginTop: 8 }}>{memberSince(user?.createdAt)}</div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', border: '1.5px solid var(--ink)', borderRadius: 13, padding: '16px 6px', marginTop: 24 }}>
              {stats.map((s) => (
                <div key={s.label} style={{ flex: 1, textAlign: 'center' }}>
                  <div className="display" style={{ fontSize: 24 }}>{s.num}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--label)', marginTop: 7, lineHeight: 1.2 }}>{s.label}</div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Link to="/list" className="btn btn-primary" style={{ fontWeight: 600 }}>List a space</Link>
              <Link to="/search" className="btn">Browse listings</Link>
              <button className="btn" onClick={logout}>Log out</button>
            </div>

            <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 13 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="label" style={{ minWidth: 74 }}>UNIVERSITY</span>
                <span style={{ fontSize: 14 }}>{user?.university || 'Not set'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="label" style={{ minWidth: 74 }}>VERIFIED</span>
                <span className="tag" style={{ borderColor: 'var(--rust)', color: 'var(--rust)' }}>
                  {user?.isVerified ? '✓ verified' : 'unverified'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span className="label" style={{ minWidth: 74 }}>EMAIL</span>
                <span className="mono" style={{ fontSize: 12.5, color: 'var(--label)' }}>{user?.email}</span>
              </div>
            </div>
          </div>

          <div style={{ flex: '1 1 480px', minWidth: 0, padding: '34px 40px 40px' }}>
            <div className="label" style={{ marginBottom: 10 }}>ABOUT</div>
            <div style={{ fontSize: 15.5, color: '#444', lineHeight: 1.6, maxWidth: '60ch' }}>
              {user?.university
                ? `Hosting and renting summer storage${user.university ? ` around ${user.university}` : ''}.`
                : 'Add a university on your account to help renters know you’re on campus.'}
            </div>

            <div className="label" style={{ margin: '30px 0 14px' }}>
              LISTINGS · {listingCount} {listingCount === 1 ? 'ACTIVE' : 'ACTIVE'}
            </div>
            {loading && <PageStatus>Loading your listings…</PageStatus>}
            {error && <PageStatus style={{ color: 'var(--rust)' }}>{error}</PageStatus>}
            {!loading && listings.length === 0 && (
              <PageStatus>
                You haven’t listed a space yet — <Link to="/list" style={{ color: 'var(--rust)' }}>publish one</Link>.
              </PageStatus>
            )}
            {listings.length > 0 && (
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {listings.map((item) => (
                  <div key={item.id} style={{ flex: '1 1 180px' }}>
                    <SpaceCard item={item} showHeart={false} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {showNotes && (
          <div style={{ padding: '14px 24px', borderTop: '1.5px solid var(--line-2)' }}>
            <Annotation>
              Profile reads GET /users/me. Listings come from GET /spaces/mine. Phone stays private until a booking is confirmed.
            </Annotation>
          </div>
        )}
      </div>
    </div>
  );
}
