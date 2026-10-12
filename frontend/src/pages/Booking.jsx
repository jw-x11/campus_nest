import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Field, LoadingState, ErrorState } from '../components/ui.jsx';
import { createBooking, estimateTotal, formatPrice, getSpace } from '../api.js';

export default function Booking() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [state, setState] = useState('loading');
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
        setState('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load listing.');
        setState('error');
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
      const booking = await createBooking({ spaceId: item.id, startDate, endDate });
      setSent(booking);
    } catch (err) {
      setError(err.message || 'Could not send booking request.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page !max-w-[880px]">
      <Link to={item ? `/space/${item.id}` : '/search'} className="mb-4 inline-block text-sm text-stone-500 hover:text-stone-900">
        ← Back to listing
      </Link>

      {state === 'loading' && <div className="card"><LoadingState label="Loading listing…" /></div>}
      {state === 'error' && <div className="card"><ErrorState message={error} /></div>}

      {state === 'ready' && item && (
        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
          <div className="card p-6">
            <h1 className="display text-2xl">Request to book</h1>
            <p className="mt-1 text-sm text-stone-500">
              {item.title} · ${formatPrice(item.price)} {item.priceUnit}
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Field label="Start date">
                <input type="date" className="input" value={startDate} min={item.availableFrom || undefined} max={item.availableTo || undefined} onChange={(e) => setStartDate(e.target.value)} />
              </Field>
              <Field label="End date">
                <input type="date" className="input" value={endDate} min={startDate || item.availableFrom || undefined} max={item.availableTo || undefined} onChange={(e) => setEndDate(e.target.value)} />
              </Field>
            </div>
            <p className="mt-2 font-mono text-[11.5px] text-stone-400">
              Must fall inside {item.availableFrom || '—'} → {item.availableTo || '—'}
            </p>
            {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
          </div>

          <aside className="card h-fit p-5">
            <p className="eyebrow">Summary</p>
            <div className="mt-3 flex justify-between text-sm">
              <span className="text-stone-500">Rate</span>
              <span className="font-medium">${formatPrice(item.price)} {item.priceUnit}</span>
            </div>
            <div className="mt-2 flex justify-between text-sm">
              <span className="text-stone-500">Dates</span>
              <span className="font-medium">{startDate || '—'} → {endDate || '—'}</span>
            </div>
            <hr className="divider my-4" />
            <div className="flex items-baseline justify-between">
              <span className="font-semibold">Est. total</span>
              <span className="display text-2xl">${formatPrice(sent?.totalPrice ?? total)}</span>
            </div>
            <p className="mt-3 rounded-xl bg-stone-50 p-3 text-[12.5px] leading-relaxed text-stone-500">
              Pay the host directly (Venmo, Zelle, cash) — payments aren&apos;t processed in the pilot.
            </p>
            {sent ? (
              <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
                <p className="font-semibold text-emerald-800">Request sent</p>
                <p className="mt-0.5 font-mono text-[11px] text-emerald-600">status: {sent.status}</p>
                <button className="btn btn-primary btn-block mt-3" onClick={() => navigate('/bookings')}>
                  View my bookings
                </button>
              </div>
            ) : (
              <button className="btn btn-primary btn-block mt-4" onClick={submit} disabled={busy || !startDate || !endDate}>
                {busy ? 'Sending…' : 'Send booking request'}
              </button>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
