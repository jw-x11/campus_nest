// Shared minimal primitives.
import { statusTone } from '../data.js';

export function Eyebrow({ children }) {
  return <div className="eyebrow">{children}</div>;
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      {label && (
        <div className="mb-1.5 flex items-baseline gap-2">
          <span className="eyebrow">{label}</span>
          {hint && <span className="font-mono text-[11px] text-stone-400">{hint}</span>}
        </div>
      )}
      {children}
    </label>
  );
}

export function StatusBadge({ status }) {
  const tone = statusTone[status] || 'bg-stone-200 text-stone-600';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] capitalize ${tone}`}
    >
      <span className="dot" />
      {status}
    </span>
  );
}

export function EmptyState({ title, body, action }) {
  return (
    <div className="px-6 py-14 text-center">
      <h3 className="display text-lg">{title}</h3>
      {body && <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-stone-500">{body}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-2 px-6 py-12 text-sm text-stone-400">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-stone-300 border-t-stone-600" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="px-6 py-12 text-center">
      <p className="text-sm text-red-700">{message || 'Something went wrong.'}</p>
      {onRetry && (
        <button className="btn btn-sm mt-4" onClick={onRetry} type="button">
          Try again
        </button>
      )}
    </div>
  );
}

export function Avatar({ children, size = 36 }) {
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.36 }}>
      {children}
    </span>
  );
}

// Compact page list: [1, …, window around current, …, last]
function pageNumbers(page, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const window = [page - 1, page, page + 1].filter((p) => p > 1 && p < totalPages);
  const pages = [1, ...window, totalPages];
  const out = [];
  let prev = 0;
  for (const p of [...new Set(pages)].sort((a, b) => a - b)) {
    if (p - prev > 1) out.push('…');
    out.push(p);
    prev = p;
  }
  return out;
}

export function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1.5 pt-6">
      <button
        className="btn btn-sm"
        disabled={page === 1}
        onClick={() => onChange(Math.max(1, page - 1))}
        type="button"
      >
        ← Prev
      </button>
      {pageNumbers(page, totalPages).map((p, i) =>
        p === '…' ? (
          <span key={`gap-${i}`} className="px-1 font-mono text-xs text-stone-300">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onChange(p)}
            aria-current={p === page ? 'page' : undefined}
            type="button"
            className={`h-8 min-w-8 rounded-lg px-2 font-mono text-[13px] transition ${
              p === page
                ? 'bg-[#2b2b2b] font-semibold text-white'
                : 'bg-white text-stone-500 shadow-sm hover:bg-stone-50'
            }`}
          >
            {p}
          </button>
        ),
      )}
      <button
        className="btn btn-sm"
        disabled={page === totalPages}
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        type="button"
      >
        Next →
      </button>
    </nav>
  );
}

export function ConfirmDialog({ open, title, body, confirmLabel = 'Confirm', danger = false, busy = false, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      onClick={onCancel}
      role="presentation"
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        className="card w-full max-w-sm p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="display text-lg">{title}</h3>
        {body && <p className="mt-2 text-sm leading-relaxed text-stone-500">{body}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn btn-sm" onClick={onCancel} disabled={busy} type="button">
            Cancel
          </button>
          <button
            className={`btn btn-sm ${danger ? 'bg-red-600 text-white !border-transparent hover:bg-red-700' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={busy}
            type="button"
            autoFocus
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
