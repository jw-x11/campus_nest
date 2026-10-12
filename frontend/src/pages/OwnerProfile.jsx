import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { SpaceCard } from '../components/cards.jsx';
import { Avatar, EmptyState, LoadingState, ErrorState, Pagination } from '../components/ui.jsx';
import { getUserProfile, listOwnerSpaces, initials, memberSince } from '../api.js';

export default function OwnerProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [owner, setOwner] = useState(null);
  const [spaces, setSpaces] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [state, setState] = useState('loading');

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    Promise.all([getUserProfile(id), listOwnerSpaces(id, page, 12)])
      .then(([u, l]) => {
        if (cancelled) return;
        setOwner(u);
        setSpaces(l.spaces);
        setTotal(l.total);
        setTotalPages(l.totalPages);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [id, page]);

  return (
    <div className="page">
      <button
        type="button"
        onClick={() => {
          if (window.history.length > 1) navigate(-1);
          else navigate('/search');
        }}
        className="mb-4 inline-block text-sm text-stone-500 hover:text-stone-900"
      >
        ← Back
      </button>

      {state === 'loading' && (
        <div className="card"><LoadingState label="Loading host…" /></div>
      )}
      {state === 'error' && (
        <div className="card"><ErrorState message="Could not load this host." /></div>
      )}

      {state === 'ready' && owner && (
        <>
          <div className="card flex flex-wrap items-center gap-5 p-6">
            {owner.avatarUrl ? (
              <img src={owner.avatarUrl} alt="" className="h-20 w-20 rounded-full border border-stone-200 object-cover" />
            ) : (
              <Avatar size={80}>{initials(owner.username)}</Avatar>
            )}
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2">
                <span className="display text-2xl">{owner.username}</span>
                {owner.isVerified && <span className="badge badge-accent">Verified</span>}
              </p>
              <p className="mt-1 font-mono text-xs text-stone-400">
                {[owner.university, memberSince(owner.createdAt)].filter(Boolean).join(' · ')}
              </p>
              {owner.description && (
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-stone-600">{owner.description}</p>
              )}
            </div>
          </div>

          <h2 className="display mb-3 mt-7 text-xl">
            Listings · {total}
          </h2>
          {spaces.length === 0 ? (
            <div className="card">
              <EmptyState title="No active listings" body="This host has nothing listed right now." />
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {spaces.map((item) => (
                  <SpaceCard key={item.id} item={item} />
                ))}
              </div>
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            </>
          )}
        </>
      )}
    </div>
  );
}
