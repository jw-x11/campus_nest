import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchIcon, ArrowRight, PinIcon, CalendarIcon } from '../components/icons.jsx';
import { SpaceCard } from '../components/cards.jsx';
import { EmptyState, LoadingState, ErrorState } from '../components/ui.jsx';
import { searchSpaces, formatPrice } from '../api.js';

const valueProps = [
  { title: 'Up to 70% cheaper', body: 'Skip the $200/mo commercial unit — rent a closet, shelf, or garage down the street.' },
  { title: 'Steps from campus', body: 'Most spaces are within a mile of campus. Search by city and filter by dates.' },
  { title: 'Flexible by the week', body: 'Weekly, monthly, or one-time pricing. No long contracts in the pilot.' },
];

const steps = [
  { num: '01', title: 'Find a space', body: 'Search nearby listings and compare price, dates, and location.' },
  { num: '02', title: 'Request your dates', body: 'Send a booking request. The host approves within about 24 hours.' },
  { num: '03', title: 'Drop off & store', body: 'Coordinate drop-off directly with your host. Pay them directly in the pilot.' },
];

function Hero({ total, minPrice }) {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  return (
    <section className="card overflow-hidden">
      <div className="bg-[#2b2b2b] px-6 py-12 text-white sm:px-12 sm:py-16">
        <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-white/50">
          Berkeley pilot · Summer 2026
        </p>
        <h1 className="display mt-3 max-w-xl text-4xl sm:text-[52px]">
          Cheap storage, right next to campus.
        </h1>
        <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-white/70">
          Rent an unused closet, shelf, garage, or room from someone nearby — cheaper and
          closer than a commercial unit.
        </p>
        <form
          className="mt-7 flex max-w-xl items-center gap-2 rounded-2xl bg-white p-2"
          onSubmit={(e) => {
            e.preventDefault();
            navigate(q.trim() ? `/search?kw=${encodeURIComponent(q.trim())}` : '/search');
          }}
        >
          <span className="pl-2 text-stone-400">
            <SearchIcon size={17} />
          </span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Try a city, e.g. Berkeley…"
            className="min-w-0 flex-1 bg-transparent text-[14.5px] text-stone-900 outline-none"
          />
          <button className="btn btn-primary btn-sm !px-5 !py-2.5" type="submit">
            Search
          </button>
        </form>
        <div className="mt-5 flex flex-wrap gap-x-6 gap-y-1 font-mono text-[12px] text-white/50">
          <span>{total == null ? '…' : total} spaces listed</span>
          {minPrice != null && <span>from ${formatPrice(minPrice)}/mo</span>}
          <span>no commission in pilot</span>
        </div>
      </div>

      <div className="grid gap-px bg-stone-100 sm:grid-cols-3">
        {valueProps.map((v) => (
          <div key={v.title} className="bg-white px-6 py-6">
            <h3 className="text-[15px] font-semibold">{v.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-stone-500">{v.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const [featured, setFeatured] = useState([]);
  const [total, setTotal] = useState(null);
  const [state, setState] = useState('loading');

  useEffect(() => {
    let cancelled = false;
    searchSpaces({ page: 1, pageSize: 6, sortBy: 'post_date', sortOrder: 'desc' })
      .then((data) => {
        if (cancelled) return;
        setFeatured(data.spaces);
        setTotal(data.total);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const minPrice = featured.length ? Math.min(...featured.map((i) => i.price)) : null;

  return (
    <div className="page flex flex-col gap-8">
      <Hero total={total} minPrice={minPrice} />

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Available now</p>
            <h2 className="display mt-1 text-2xl">Spaces near campus</h2>
          </div>
          <button className="btn btn-sm" onClick={() => navigate('/search')}>
            See all <ArrowRight size={13} />
          </button>
        </div>
        {state === 'loading' && (
          <div className="card"><LoadingState label="Loading spaces…" /></div>
        )}
        {state === 'error' && (
          <div className="card"><ErrorState message="Could not load spaces." onRetry={() => window.location.reload()} /></div>
        )}
        {state === 'ready' && featured.length === 0 && (
          <div className="card">
            <EmptyState
              title="No listings yet"
              body="Be the first to list a space for the summer."
              action={<a href="/list" target="_blank" rel="noreferrer" className="btn btn-primary">List your space</a>}
            />
          </div>
        )}
        {state === 'ready' && featured.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((item) => (
              <SpaceCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </section>

      <section className="card p-6 sm:p-10">
        <p className="eyebrow">How it works</p>
        <h2 className="display mt-1 text-2xl">Store in three steps</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {steps.map((s) => (
            <div key={s.num} className="rounded-2xl bg-stone-50 p-5">
              <span className="badge badge-accent">{s.num}</span>
              <h3 className="mt-3 font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-stone-500">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="card flex flex-wrap items-center justify-between gap-5 bg-[#ffd22e] !border-transparent p-6 sm:p-10">
        <div>
          <h2 className="display text-2xl">Have an empty closet?</h2>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-stone-700">
            <span className="inline-flex items-center gap-1.5"><PinIcon size={13} /> Free to list</span>
            <span className="inline-flex items-center gap-1.5"><CalendarIcon size={13} /> You approve every booking</span>
          </p>
        </div>
        <a href="/list" target="_blank" rel="noreferrer" className="btn btn-dark">
          List your space <ArrowRight size={14} />
        </a>
      </section>
    </div>
  );
}
