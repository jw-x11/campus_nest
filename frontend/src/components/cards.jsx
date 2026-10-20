import { useNavigate } from 'react-router-dom';
import { HeartIcon, BoxIcon, PinIcon, CalendarIcon } from './icons.jsx';
import { useApp } from '../context/AppContext.jsx';
import { formatPrice } from '../api.js';

export function SaveButton({ id }) {
  const { user, isSaved, toggleSaved } = useApp();
  const navigate = useNavigate();
  const saved = isSaved(id);
  return (
    <button
      type="button"
      aria-label={saved ? 'Remove from saved' : 'Save this space'}
      aria-pressed={saved}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!user) {
          navigate(`/login?next=${encodeURIComponent(`/space/${id}`)}`);
          return;
        }
        toggleSaved(id).catch(() => {});
      }}
      className={`grid h-8 w-8 flex-none place-items-center rounded-full border transition ${
        saved
          ? 'border-transparent bg-[#ffd22e] text-[#2b2b2b]'
          : 'border-stone-200 bg-white text-stone-500 hover:border-stone-300 hover:text-[#2b2b2b]'
      }`}
    >
      <HeartIcon size={14} filled={saved} />
    </button>
  );
}

export function Photo({ item, className = '', iconSize = 30 }) {
  if (item.thumbnailUrl) {
    return (
      <img
        src={item.thumbnailUrl}
        alt=""
        loading="lazy"
        className={`object-cover ${className}`}
      />
    );
  }
  const first = item.images?.[0];
  if (first) {
    return <img src={first} alt="" loading="lazy" className={`object-cover ${className}`} />;
  }
  return (
    <div className={`photo-fallback ${className}`}>
      <BoxIcon size={iconSize} />
    </div>
  );
}

// Vertical card — landing grids, saved.
export function SpaceCard({ item }) {
  const navigate = useNavigate();
  return (
    <article
      onClick={() => navigate(`/space/${item.id}`)}
      className="card card-hover clickable overflow-hidden"
    >
      <div className="relative">
        <Photo item={item} className="aspect-[16/10] w-full" />
        <div className="absolute left-3 top-3">
          <span className="badge bg-white/90 backdrop-blur">{item.priceTypeLabel}</span>
        </div>
      </div>
      <div className="p-4">
        <h3 className="truncate text-[15px] font-semibold">{item.title}</h3>
        <p className="mt-1 flex items-center gap-1 truncate font-mono text-[11.5px] text-stone-500">
          <PinIcon size={12} />
          {item.location || '—'}
        </p>
        {item.dateRange && (
          <p className="mt-0.5 flex items-center gap-1 truncate font-mono text-[11.5px] text-stone-500">
            <CalendarIcon size={12} />
            {item.dateRange}
          </p>
        )}
        <div className="mt-3 flex items-baseline justify-between">
          <span className="display text-xl">
            ${formatPrice(item.price)}
            <span className="ml-0.5 text-xs font-normal text-stone-400">{item.priceUnit}</span>
          </span>
          <span className="font-mono text-[11px] text-stone-400">{item.viewCount} views</span>
        </div>
      </div>
    </article>
  );
}

// Horizontal row — search results, map list, history. By default a click opens the listing;
// onClick replaces that (the map page zooms to the pin instead).
// hoverable: false leaves the background to the parent, for example to keep a selected highlight.
export function SpaceRow({ item, onClick, hoverable = true }) {
  const navigate = useNavigate();
  return (
    <article
      onClick={onClick ?? (() => navigate(`/space/${item.id}`))}
      className={`clickable flex items-center gap-4 border-b border-stone-100 px-5 py-4 transition last:border-0 ${
        hoverable ? 'hover:bg-stone-50' : ''
      }`}
    >
      <Photo item={item} className="h-20 w-20 flex-none rounded-xl" iconSize={22} />
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-[15px] font-semibold">{item.title}</h3>
        <p className="mt-0.5 truncate font-mono text-[11.5px] text-stone-500">
          {item.subtitle || item.city || '—'}
        </p>
        <div className="mt-2 flex items-center gap-2">
          <span className="badge">{item.priceTypeLabel}</span>
          {item.notAccepting && <span className="badge">Paused</span>}
        </div>
      </div>
      <div className="flex-none">
        <span className="display text-lg">
          ${formatPrice(item.price)}
          <span className="text-xs font-normal text-stone-400">{item.priceUnit}</span>
        </span>
      </div>
    </article>
  );
}
