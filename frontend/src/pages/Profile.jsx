import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Avatar, Field, ConfirmDialog, EmptyState, LoadingState, ErrorState } from '../components/ui.jsx';
import { Photo } from '../components/cards.jsx';
import { useApp } from '../context/AppContext.jsx';
import {
  deleteSpace,
  formatPrice,
  initials,
  listMySpaces,
  memberSince,
  renewSpace,
  setSpaceAccepting,
  storeUser,
  updateMe,
  uploadAvatar,
} from '../api.js';

function listingStatus(item) {
  if (!item.isActive) return { label: 'Hidden', accent: false };
  if (item.expiredAt && new Date(item.expiredAt) <= new Date()) return { label: 'Expired', accent: false };
  if (item.notAccepting) return { label: 'Paused', accent: false };
  return { label: 'Live', accent: true };
}

function ListingCard({ item, onChanged }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(null); // 'pause' | 'delete' | null
  const isExpired = item.expiredAt ? new Date(item.expiredAt) <= new Date() : false;

  const run = async (label, fn) => {
    setBusy(label);
    setError('');
    try {
      await fn();
      setConfirming(null);
      onChanged();
    } catch (err) {
      setError(err.message || 'Action failed.');
      setConfirming(null);
    } finally {
      setBusy('');
    }
  };

  const status = listingStatus(item);

  return (
    <article className="card overflow-hidden">
      <Link to={`/space/${item.id}`} className="relative block">
        <Photo item={item} className="aspect-[16/10] w-full" />
        <div className="absolute left-3 top-3">
          <span className={`badge ${status.accent ? 'badge-accent' : 'bg-white/90 backdrop-blur'}`}>
            {status.label}
          </span>
        </div>
      </Link>
      <div className="p-4">
        <Link to={`/space/${item.id}`} className="block truncate text-[15px] font-semibold hover:underline">
          {item.title}
        </Link>
        <p className="mt-1 truncate font-mono text-[11.5px] text-stone-500">
          {item.subtitle || item.city || '—'}
        </p>
        <div className="mt-3 flex items-baseline justify-between">
          <span className="display text-xl">
            ${formatPrice(item.price)}
            <span className="ml-0.5 text-xs font-normal text-stone-400">{item.priceUnit}</span>
          </span>
          <span className="font-mono text-[11px] text-stone-400">{item.viewCount} views</span>
        </div>
        {error && <p className="mt-2 text-[13px] text-red-700">{error}</p>}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {item.notAccepting ? (
            <button
              className="btn btn-sm" disabled={!!busy}
              onClick={() => run('accepting', () => setSpaceAccepting(item.id, false))}
            >
              {busy === 'accepting' ? '…' : 'Resume requests'}
            </button>
          ) : (
            <button
              className="btn btn-sm" disabled={!!busy}
              onClick={() => setConfirming('pause')}
            >
              Pause requests
            </button>
          )}
          {isExpired && (
            <button className="btn btn-sm" disabled={!!busy} onClick={() => run('renew', () => renewSpace(item.id))}>
              {busy === 'renew' ? '…' : 'Renew'}
            </button>
          )}
          <button className="btn btn-sm" disabled={!!busy} onClick={() => setConfirming('delete')}>
            Delete
          </button>
          <Link to={`/edit/${item.id}`} className="btn btn-sm">
            Edit
          </Link>
        </div>
      </div>
      <ConfirmDialog
        open={confirming === 'pause'}
        title="Pause requests?"
        body="Your listing stays visible, but renters won't be able to send new booking requests. You can resume anytime."
        confirmLabel="Pause requests"
        busy={busy === 'accepting'}
        onCancel={() => setConfirming(null)}
        onConfirm={() => run('accepting', () => setSpaceAccepting(item.id, true))}
      />
      <ConfirmDialog
        open={confirming === 'delete'}
        title="Delete this listing?"
        body="It will be hidden from search. Existing bookings are kept."
        confirmLabel="Delete listing"
        danger
        busy={busy === 'delete'}
        onCancel={() => setConfirming(null)}
        onConfirm={() => run('delete', () => deleteSpace(item.id))}
      />
    </article>
  );
}

export default function Profile() {
  const { user, setUser, logout, saved } = useApp();
  const [listings, setListings] = useState([]);
  const [listingCount, setListingCount] = useState(0);
  const [state, setState] = useState('loading');
  const [listError, setListError] = useState('');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ username: '', phone: '', university: '', description: '' });
  const [saveState, setSaveState] = useState('');
  const [avatarBusy, setAvatarBusy] = useState(false);

  const loadListings = async () => {
    try {
      const data = await listMySpaces(1, 12);
      setListings(data.spaces);
      setListingCount(data.total);
      setState('ready');
    } catch (err) {
      setListError(err.message || 'Could not load your listings.');
      setState('error');
    }
  };

  useEffect(() => {
    loadListings();
  }, []);

  useEffect(() => {
    if (user) {
      setForm({
        username: user.username || '',
        phone: user.phone || '',
        university: user.university || '',
        description: user.description || '',
      });
    }
  }, [user]);

  const saveProfile = async (e) => {
    e.preventDefault();
    setSaveState('saving');
    try {
      const words = form.description.trim().split(/\s+/).filter(Boolean).length;
      if (form.description.trim() && words > 200) throw new Error('Description must be 200 words or less.');
      const updated = await updateMe({
        username: form.username.trim() || undefined,
        phone: form.phone.trim() || undefined,
        university: form.university.trim() || undefined,
        description: form.description.trim() || undefined,
      });
      setUser(updated);
      storeUser(updated);
      setEditing(false);
      setSaveState('saved');
      setTimeout(() => setSaveState(''), 2500);
    } catch (err) {
      setSaveState('');
      alert(err.message || 'Could not save profile.');
    }
  };

  const onAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarBusy(true);
    try {
      const updated = await uploadAvatar(file);
      setUser(updated);
    } catch (err) {
      alert(err.message || 'Avatar upload failed.');
    } finally {
      setAvatarBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        {/* identity card */}
        <div className="card h-fit p-6 text-center">
          <div className="flex flex-col items-center">
            {user?.avatarUrl ? (
              <img src={user.avatarUrl} alt="" className="h-24 w-24 rounded-full border border-stone-200 object-cover" />
            ) : (
              <Avatar size={88}>{initials(user?.username)}</Avatar>
            )}
            <label className="mt-3 cursor-pointer font-mono text-[11.5px] text-stone-400 hover:text-stone-700">
              {avatarBusy ? 'Uploading…' : 'Change photo'}
              <input type="file" accept="image/*" className="hidden" onChange={onAvatar} />
            </label>
            <h1 className="display mt-2 text-2xl">{user?.username}</h1>
            <p className="text-sm text-stone-500">{user?.university || user?.email}</p>
            <p className="mt-1 font-mono text-[11px] text-stone-400">{memberSince(user?.createdAt)}</p>
            <span className={`badge mt-3 ${user?.isVerified ? 'badge-accent' : ''}`}>
              {user?.isVerified ? 'Verified' : 'Unverified'}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-3 divide-x divide-stone-100 rounded-xl bg-stone-50 py-3">
            {[
              [String(listingCount), 'Listings'],
              [String(saved.size), 'Saved'],
              [user?.isVerified ? 'Yes' : 'No', 'Verified'],
            ].map(([num, label]) => (
              <div key={label}>
                <div className="display text-xl">{num}</div>
                <div className="eyebrow mt-0.5">{label}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-2">
            <Link to="/list" className="btn btn-primary btn-block">List a space</Link>
            <Link to="/bookings" className="btn btn-block">My bookings</Link>
            <Link to="/history" className="btn btn-block">Recently viewed</Link>
            <button className="btn btn-block" onClick={logout}>Log out</button>
          </div>
        </div>

        {/* details + listings */}
        <div className="min-w-0">
          <div className="card p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Profile</h2>
              <button className="btn btn-sm" onClick={() => setEditing((v) => !v)}>
                {editing ? 'Cancel' : 'Edit'}
              </button>
            </div>
            {editing ? (
              <form onSubmit={saveProfile} className="mt-4 grid gap-4 sm:grid-cols-2">
                <Field label="Username">
                  <input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
                </Field>
                <Field label="Phone">
                  <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+1…" />
                </Field>
                <Field label="University">
                  <input className="input" value={form.university} onChange={(e) => setForm({ ...form, university: e.target.value })} placeholder="State U" />
                </Field>
                <div className="sm:col-span-2">
                  <Field label="About" hint="max 200 words">
                    <textarea className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Junior with a dry basement closet two blocks from campus." />
                  </Field>
                </div>
                <div className="sm:col-span-2">
                  <button className="btn btn-primary" type="submit" disabled={saveState === 'saving'}>
                    {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved ✓' : 'Save changes'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="mt-3 space-y-2.5 text-sm">
                <p><span className="eyebrow mr-2">Email</span><span className="font-mono text-[12.5px] text-stone-500">{user?.email}</span></p>
                <p><span className="eyebrow mr-2">Phone</span>{user?.phone || <span className="text-stone-400">Not set</span>}</p>
                <p><span className="eyebrow mr-2">University</span>{user?.university || <span className="text-stone-400">Not set</span>}</p>
                <p className="leading-relaxed text-stone-600">{user?.description || 'No bio yet — add one so renters know you.'}</p>
              </div>
            )}
          </div>

          <div className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="display text-xl">My listings · {listingCount}</h2>
              <Link to="/list" className="btn btn-sm">+ New</Link>
            </div>
            {state === 'loading' && <div className="card"><LoadingState label="Loading your listings…" /></div>}
            {state === 'error' && <div className="card"><ErrorState message={listError} onRetry={loadListings} /></div>}
            {state === 'ready' && listings.length === 0 && (
              <div className="card">
                <EmptyState
                  title="No listings yet"
                  body="Publish your first space — it takes about a minute."
                  action={<Link to="/list" className="btn btn-primary">List your space</Link>}
                />
              </div>
            )}
            {state === 'ready' && listings.length > 0 && (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {listings.map((item) => (
                  <ListingCard key={item.id} item={item} onChanged={loadListings} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
