import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { BoxIcon, PinIcon, CalendarIcon } from '../components/icons.jsx';
import { SaveButton } from '../components/cards.jsx';
import { LoadingState, ErrorState, StatusBadge } from '../components/ui.jsx';
import { useApp } from '../context/AppContext.jsx';
import { formatDateRange, formatPrice, getSpace, recordView } from '../api.js';

function Gallery({ images, thumbnail }) {
  const [idx, setIdx] = useState(0);
  const list = images?.length ? images : thumbnail ? [thumbnail] : [];
  if (!list.length) {
    return (
      <div className="photo-fallback aspect-[16/8] w-full rounded-2xl">
        <BoxIcon size={44} />
      </div>
    );
  }
  return (
    <div>
      <div className="overflow-hidden rounded-2xl bg-stone-100">
        <img src={list[idx]} alt="" className="aspect-[16/8] w-full object-cover" />
      </div>
      {list.length > 1 && (
        <div className="mt-2 flex gap-2 overflow-x-auto">
          {list.map((src, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setIdx(i)}
              className={`h-16 w-24 flex-none overflow-hidden rounded-xl border-2 transition ${
                i === idx ? 'border-[#2b2b2b]' : 'border-transparent opacity-60 hover:opacity-100'
              }`}
            >
              <img src={src} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SpaceDetail() {
  const { id } = useParams();
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

  useEffect(() => {
    if (!user || !item || user.id === item.ownerId) return;
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
          </aside>
        </div>
      )}
    </div>
  );
}
