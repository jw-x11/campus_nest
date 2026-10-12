import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { BoxIcon, PinIcon, CalendarIcon, XIcon } from '../components/icons.jsx';
import { SaveButton } from '../components/cards.jsx';
import { Avatar, LoadingState, ErrorState, StatusBadge } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import {
  formatDateRange,
  formatPrice,
  getSpace,
  getUserProfile,
  initials,
  memberSince,
  recordView,
} from '../api.js';

function Arrow({ side, onClick, label }) {
  return (
    <button
      type="button"
      aria-label={label || (side === 'left' ? 'Previous photo' : 'Next photo')}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`absolute top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-xl leading-none text-stone-700 shadow-md transition hover:scale-105 hover:bg-white ${
        side === 'left' ? 'left-3' : 'right-3'
      } sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100`}
    >
      {side === 'left' ? '‹' : '›'}
    </button>
  );
}

function Gallery({ images, thumbnail }) {
  const [idx, setIdx] = useState(0);
  const [dir, setDir] = useState(0);
  const [lightbox, setLightbox] = useState(false);
  const list = images?.length ? images : thumbnail ? [thumbnail] : [];

  const go = (next) => {
    if (list.length < 2) return;
    const n = (next + list.length) % list.length;
    if (n === idx) return;
    // Direction for the slide animation (handles wrap-around).
    if (next === idx + 1 || (idx === list.length - 1 && next === -1)) setDir(1);
    else if (next === idx - 1 || (idx === 0 && next === list.length)) setDir(-1);
    else setDir(0);
    setIdx(n);
  };

  // Keyboard nav + scroll lock while the lightbox is open.
  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setLightbox(false);
      else if (e.key === 'ArrowRight') go(idx + 1);
      else if (e.key === 'ArrowLeft') go(idx - 1);
    };
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  });

  if (!list.length) {
    return (
      <div className="photo-fallback aspect-[16/8] w-full rounded-2xl">
        <BoxIcon size={44} />
      </div>
    );
  }
  return (
    <div>
      <div
        className="group relative cursor-zoom-in overflow-hidden rounded-2xl bg-stone-100"
        onClick={() => setLightbox(true)}
        role="button"
        aria-label="Enlarge photos"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter') setLightbox(true);
        }}
      >
        <img
          key={list[idx]}
          src={list[idx]}
          alt=""
          style={{ '--slide': `${dir * 28}px` }}
          className="gallery-img aspect-[16/8] w-full object-cover"
        />
        {list.length > 1 && (
          <>
            <Arrow side="left" onClick={() => go(idx - 1)} />
            <Arrow side="right" onClick={() => go(idx + 1)} />
            <span className="absolute bottom-3 right-3 rounded-full bg-black/55 px-2.5 py-1 font-mono text-[11px] text-white">
              {idx + 1} / {list.length}
            </span>
          </>
        )}
      </div>
      {list.length > 1 && (
        <div className="mt-2 flex gap-2 overflow-x-auto pb-0.5">
          {list.map((src, i) => (
            <button
              key={i}
              type="button"
              onClick={() => go(i)}
              aria-label={`Photo ${i + 1}`}
              className={`h-12 w-20 flex-none overflow-hidden rounded-lg border-2 transition ${
                i === idx ? 'border-[#2b2b2b]' : 'border-transparent opacity-55 hover:opacity-100'
              }`}
            >
              <img src={src} alt="" loading="lazy" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex flex-col bg-black/92 p-4 sm:p-8"
          onClick={() => setLightbox(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Photo viewer"
        >
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between py-2 text-white">
            <span className="font-mono text-xs text-white/70">
              {idx + 1} / {list.length}
            </span>
            <button
              type="button"
              aria-label="Close viewer"
              onClick={() => setLightbox(false)}
              className="grid h-10 w-10 place-items-center rounded-full bg-white/10 text-white transition hover:bg-white/20"
            >
              <XIcon size={16} />
            </button>
          </div>
          <div
            className="group relative mx-auto flex min-h-0 w-full max-w-5xl flex-1 items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              key={list[idx]}
              src={list[idx]}
              alt=""
              style={{ '--slide': `${dir * 40}px` }}
              className="gallery-img max-h-[68vh] w-auto max-w-full rounded-xl object-contain"
            />
            {list.length > 1 && (
              <>
                <Arrow side="left" onClick={() => go(idx - 1)} />
                <Arrow side="right" onClick={() => go(idx + 1)} />
              </>
            )}
          </div>
          {list.length > 1 && (
            <div
              className="mx-auto mt-4 flex w-full max-w-5xl justify-center gap-2 overflow-x-auto"
              onClick={(e) => e.stopPropagation()}
            >
              {list.map((src, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => go(i)}
                  aria-label={`Photo ${i + 1}`}
                  className={`h-12 w-20 flex-none overflow-hidden rounded-lg border-2 transition ${
                    i === idx ? 'border-white' : 'border-transparent opacity-45 hover:opacity-90'
                  }`}
                >
                  <img src={src} alt="" loading="lazy" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OwnerCard({ ownerId, isOwner, selfUser }) {
  const [owner, setOwner] = useState(null);

  useEffect(() => {
    if (isOwner || !ownerId) return;
    let cancelled = false;
    getUserProfile(ownerId)
      .then((u) => {
        if (!cancelled) setOwner(u);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [ownerId, isOwner]);

  if (isOwner && selfUser) {
    return (
      <div className="card mt-4 flex items-center gap-4 p-5">
        <Avatar size={48}>{initials(selfUser.username)}</Avatar>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Listed by you</p>
          <p className="truncate text-sm text-stone-500">{selfUser.username}</p>
        </div>
        <Link to="/profile" className="btn btn-sm flex-none">Manage</Link>
      </div>
    );
  }

  if (!owner) return null;

  return (
    <div className="card mt-4 p-5">
      <p className="eyebrow">Listed by</p>
      <div className="mt-3 flex items-center gap-4">
        {owner.avatarUrl ? (
          <img src={owner.avatarUrl} alt="" className="h-12 w-12 rounded-full border border-stone-200 object-cover" />
        ) : (
          <Avatar size={48}>{initials(owner.username)}</Avatar>
        )}
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 font-semibold">
            {owner.username}
            {owner.isVerified && <span className="badge badge-accent">Verified</span>}
          </p>
          <p className="mt-0.5 truncate font-mono text-[11.5px] text-stone-400">
            {[owner.university, memberSince(owner.createdAt)].filter(Boolean).join(' · ')}
          </p>
        </div>
      </div>
      {owner.description && (
        <p className="mt-3 text-sm leading-relaxed text-stone-600">{owner.description}</p>
      )}
      <div className="mt-4 flex gap-2">
        <Link to={`/owner/${owner.id}`} className="btn btn-sm flex-1">View all listings</Link>
        <Link to="/messages" className="btn btn-sm flex-1">Message</Link>
      </div>
    </div>
  );
}

export default function SpaceDetail() {  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useApp();
  const [item, setItem] = useState(null);
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const isOwner = Boolean(user && item && String(user.id) === String(item.ownerId));

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    getSpace(id)
      .then((space) => {
        if (cancelled) return;
        setItem(space);
        setState('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.status === 404 ? 'This listing was not found.' : err.message || 'Could not load listing.');
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const recordedRef = useRef(null);
  useEffect(() => {
    if (!user || !item || user.id === item.ownerId) return;
    if (recordedRef.current === item.id) return; // one view per listing view
    recordedRef.current = item.id;
    recordView(item.id).catch(() => {});
  }, [user, item]);

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
        <div className="card"><LoadingState label="Loading listing…" /></div>
      )}
      {state === 'error' && (
        <div className="card"><ErrorState message={error} onRetry={() => window.location.reload()} /></div>
      )}

      {state === 'ready' && item && (
        <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
          <div className="min-w-0">
            <Gallery images={item.images} thumbnail={item.thumbnailUrl} />
            <div className="card mt-4 p-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="badge">{item.priceTypeLabel}</span>
                {item.notAccepting && <span className="badge">Paused — not taking requests</span>}
                {!item.isActive && <span className="badge">Hidden</span>}
              </div>
              <h1 className="display mt-3 text-3xl">{item.title}</h1>
              <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-stone-500">
                <span className="inline-flex items-center gap-1.5">
                  <PinIcon size={13} /> {item.city || '—'}{item.postalCode ? ` · ${item.postalCode}` : ''}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CalendarIcon size={13} /> {formatDateRange(item.availableFrom, item.availableTo) || '—'}
                </span>
                <span className="font-mono text-xs text-stone-400">{item.viewCount} views</span>
              </p>
              <hr className="divider my-5" />
              <h2 className="font-semibold">About this space</h2>
              <p className="mt-2 text-[15px] leading-relaxed text-stone-600">
                {item.description || 'The host has not added a description yet.'}
              </p>
              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ['City', item.city || '—'],
                  ['Price', `$${formatPrice(item.price)} ${item.priceUnit}`],
                  ['Available', formatDateRange(item.availableFrom, item.availableTo) || '—'],
                  ['Views', String(item.viewCount)],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-stone-50 p-3">
                    <div className="eyebrow">{k}</div>
                    <div className="mt-1 truncate text-sm font-medium">{v}</div>
                  </div>
                ))}
              </div>
              <div className="mt-5 rounded-xl bg-stone-50 p-4 text-[13px] leading-relaxed text-stone-500">
                Showing an approximate area only — the exact address is shared after the host
                confirms your booking.
              </div>
            </div>
          </div>

          <aside className="h-fit lg:sticky lg:top-20">
            <div className="card p-5">
              <div className="flex items-baseline gap-1.5">
                <span className="display text-3xl">${formatPrice(item.price)}</span>
                <span className="text-sm text-stone-400">{item.priceUnit}</span>
              </div>
              <p className="mt-1 font-mono text-[11.5px] text-stone-400">
                {formatDateRange(item.availableFrom, item.availableTo)}
              </p>
              {isOwner ? (
                <div className="mt-4">
                  <StatusBadge status={item.notAccepting ? 'paused' : 'active'} />
                  <p className="mt-2 text-[13px] text-stone-500">This is your listing.</p>
                  <Link to="/profile" className="btn btn-block mt-3">Manage listing</Link>
                </div>
              ) : item.notAccepting ? (
                <div className="mt-4 rounded-xl bg-stone-50 p-3 text-[13px] text-stone-500">
                  This host has paused new requests for now. Save it and check back later.
                </div>
              ) : (
                <button className="btn btn-primary btn-block mt-4" onClick={() => navigate(`/book/${item.id}`)}>
                  Request to book
                </button>
              )}
              <div className="mt-2 flex gap-2">
                <span className="btn flex-1 !px-2">
                  <SaveButton id={item.id} /> Save
                </span>
                <Link to="/messages" className="btn flex-1">Message</Link>
              </div>
              <p className="mt-3 text-center text-xs leading-relaxed text-stone-400">
                You won&apos;t be charged yet.
                <br />Host approves within ~24h.
              </p>
            </div>
            <OwnerCard ownerId={item.ownerId} isOwner={isOwner} selfUser={user} />
          </aside>
        </div>
      )}
    </div>
  );
}
