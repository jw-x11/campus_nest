import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { StatusBadge, EmptyState, LoadingState, ErrorState } from '../components/ui.jsx';
import { bookingStatuses } from '../data.js';
import {
  acceptBooking,
  cancelBooking,
  confirmBooking,
  declineBooking,
  formatDate,
  formatPrice,
  getSpace,
  listBookings,
  setSpecialDeal,
  updateBooking,
  withdrawCancel,
} from '../api.js';

const spaceTitleCache = new Map();

async function spaceTitle(spaceId) {
  const key = String(spaceId);
  if (spaceTitleCache.has(key)) return spaceTitleCache.get(key);
  try {
    const s = await getSpace(key);
    spaceTitleCache.set(key, s.title);
    return s.title;
  } catch {
    return `Space #${key}`;
  }
}

function useSpaceTitles(bookings) {
  const [titles, setTitles] = useState({});
  useEffect(() => {
    let cancelled = false;
    const ids = [...new Set(bookings.map((b) => String(b.spaceId)))];
    Promise.all(ids.map((id) => spaceTitle(id).then((t) => [id, t]))).then((pairs) => {
      if (!cancelled) setTitles(Object.fromEntries(pairs));
    });
    return () => {
      cancelled = true;
    };
  }, [bookings]);
  return titles;
}

function BookingCard({ booking, titles, role, onChanged }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [deal, setDeal] = useState('');
  const [start, setStart] = useState(booking.startDate);
  const [end, setEnd] = useState(booking.endDate);

  const run = async (label, fn) => {
    setBusy(label);
    setError('');
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(err.message || 'Action failed.');
    } finally {
      setBusy('');
    }
  };

  const isRenter = role === 'renter';
  const editable = ['pending', 'accepted'].includes(booking.status);
  const cancellableNow = ['pending', 'accepted'].includes(booking.status);
  const needsAgreement = ['confirmed', 'active'].includes(booking.status);

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to={`/space/${booking.spaceId}`} className="font-semibold hover:underline">
            {titles[String(booking.spaceId)] || `Space #${booking.spaceId}`}
          </Link>
          <p className="mt-0.5 font-mono text-[11.5px] text-stone-400">
            {formatDate(booking.startDate)} → {formatDate(booking.endDate)} · ${formatPrice(booking.totalPrice)} total
            {booking.specialDeal > 0 && ` · deal $${formatPrice(booking.specialDeal)}`}
          </p>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      {needsAgreement && booking.cancelRequestedBy && (
        <p className="mt-3 rounded-xl bg-amber-50 p-3 text-[13px] text-amber-800">
          Cancel requested by {booking.cancelRequestedBy}
          {booking.cancelRequestedBy === role ? ' (you — you can withdraw it)' : ' — your confirmation will cancel it'}.
        </p>
      )}

      {error && <p className="mt-3 text-[13px] text-red-700">{error}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        {cancellableNow && (
          <button className="btn btn-sm" disabled={!!busy} onClick={() => run('cancel', () => cancelBooking(booking.id))}>
            {busy === 'cancel' ? 'Working…' : 'Cancel booking'}
          </button>
        )}
        {needsAgreement && (
          <>
            <button className="btn btn-sm" disabled={!!busy} onClick={() => run('cancel', () => cancelBooking(booking.id))}>
              {busy === 'cancel' ? 'Working…' : booking.cancelRequestedBy ? 'Agree to cancel' : 'Request cancel'}
            </button>
            {booking.cancelRequestedBy === role && (
              <button className="btn btn-sm" disabled={!!busy} onClick={() => run('withdraw', () => withdrawCancel(booking.id))}>
                {busy === 'withdraw' ? 'Working…' : 'Withdraw request'}
              </button>
            )}
          </>
        )}
        {isRenter && editable && (
          <button className="btn btn-sm" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Close date editor' : 'Change dates'}
          </button>
        )}
        {!isRenter && booking.status === 'pending' && (
          <>
            <button className="btn btn-sm btn-primary" disabled={!!busy} onClick={() => run('accept', () => acceptBooking(booking.id))}>
              {busy === 'accept' ? 'Working…' : 'Accept'}
            </button>
            <button className="btn btn-sm" disabled={!!busy} onClick={() => run('decline', () => declineBooking(booking.id))}>
              {busy === 'decline' ? 'Working…' : 'Decline'}
            </button>
          </>
        )}
        {!isRenter && booking.status === 'accepted' && (
          <>
            <button className="btn btn-sm btn-primary" disabled={!!busy} onClick={() => run('confirm', () => confirmBooking(booking.id))}>
              {busy === 'confirm' ? 'Working…' : 'Confirm'}
            </button>
            <span className="inline-flex items-center gap-1.5">
              <input
                className="input !w-28 !py-1.5 text-[13px]"
                type="number" min="0.01" step="0.01" placeholder="Deal $"
                value={deal} onChange={(e) => setDeal(e.target.value)}
              />
              <button className="btn btn-sm" disabled={!!busy || !deal} onClick={() => run('deal', () => setSpecialDeal(booking.id, deal).then(() => setDeal('')))}>
                {busy === 'deal' ? '…' : 'Set deal'}
              </button>
            </span>
          </>
        )}
      </div>

      {editing && (
        <div className="mt-4 grid gap-2 rounded-xl bg-stone-50 p-3 sm:grid-cols-[1fr_1fr_auto]">
          <input type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
          <input type="date" className="input" value={end} min={start} onChange={(e) => setEnd(e.target.value)} />
          <button
            className="btn btn-sm btn-dark"
            disabled={!!busy}
            onClick={() => run('dates', () => updateBooking(booking.id, { startDate: start, endDate: end }).then(() => setEditing(false)))}
          >
            {busy === 'dates' ? 'Saving…' : 'Save'}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Bookings() {
  const [view, setView] = useState('renter');
  const [status, setStatus] = useState('pending');
  const [bookings, setBookings] = useState([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState('loading');

  const load = useCallback(async () => {
    setState('loading');
    try {
      const data = await listBookings({ view, status, page: 1, pageSize: 20 });
      setBookings(data.bookings);
      setTotal(data.total);
      setState('ready');
    } catch {
      setState('error');
    }
  }, [view, status]);

  useEffect(() => {
    load();
  }, [load]);

  const titles = useSpaceTitles(bookings);
  const statusOptions = useMemo(() => bookingStatuses, []);

  return (
    <div className="page">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Bookings</p>
          <h1 className="display mt-1 text-3xl">{view === 'renter' ? 'My requests' : 'Requests for my spaces'}</h1>
        </div>
        <div className="flex gap-1 rounded-xl bg-white p-1 shadow-sm">
          {['renter', 'owner'].map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold capitalize transition ${
                view === v ? 'bg-[#2b2b2b] text-white' : 'text-stone-400 hover:text-stone-700'
              }`}
            >
              {v === 'renter' ? 'As renter' : 'As host'}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {statusOptions.map((s) => (
          <button
            key={s.value}
            onClick={() => setStatus(s.value)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
              status === s.value ? 'bg-[#ffd22e]' : 'bg-white text-stone-500 shadow-sm hover:bg-stone-50'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {state === 'loading' && <div className="card"><LoadingState label="Loading bookings…" /></div>}
      {state === 'error' && <div className="card"><ErrorState message="Could not load bookings." onRetry={load} /></div>}
      {state === 'ready' && bookings.length === 0 && (
        <div className="card">
          <EmptyState
            title={`No ${status} bookings`}
            body={view === 'renter' ? 'Find a space and send your first request.' : 'When renters request your spaces, they will show up here.'}
            action={<Link to="/search" className="btn btn-primary">Browse spaces</Link>}
          />
        </div>
      )}
      {state === 'ready' && bookings.length > 0 && (
        <>
          <p className="mb-3 font-mono text-xs text-stone-400">{total} booking{total === 1 ? '' : 's'}</p>
          <div className="grid gap-3">
            {bookings.map((b) => (
              <BookingCard key={b.id} booking={b} titles={titles} role={view} onChanged={load} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
