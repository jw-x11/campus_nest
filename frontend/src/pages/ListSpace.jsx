import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Field, LoadingState, ErrorState } from '../components/ui.jsx';
import { XIcon } from '../components/icons.jsx';
import AddressInput from '../components/AddressInput.jsx';
import { formPriceTypes, stateCode, US_STATES } from '../data.js';
import { closeTabOr } from '../utils.js';
import { createSpace, getSpace, updateSpace, uploadSpaceImages } from '../api.js';

const MAX_IMAGES = 10;

const EMPTY = {
  title: '', description: '', address: '', city: '', state: '', postalCode: '',
  // Set when the address was picked from the suggestions, so the server needs no geocoding.
  latitude: null, longitude: null,
  price: '', priceType: 'recurring_per_month', availableFrom: '', availableTo: '',
};

// One preview URL per picked file. Creating it during render made a new blob URL (and a new
// image request) on every keystroke in the form, and none of them were ever released.
const previewUrls = new WeakMap();

function previewUrl(file) {
  let url = previewUrls.get(file);
  if (!url) {
    url = URL.createObjectURL(file);
    previewUrls.set(file, url);
  }
  return url;
}

function releasePreview(file) {
  const url = previewUrls.get(file);
  if (url) {
    URL.revokeObjectURL(url);
    previewUrls.delete(file);
  }
}

function PhotoPicker({ files, onAdd, onRemove, existingCount }) {
  const remaining = MAX_IMAGES - existingCount - files.length;

  // Release whatever previews are left when the form closes.
  const filesRef = useRef(files);
  useEffect(() => {
    filesRef.current = files;
  }, [files]);
  useEffect(() => () => filesRef.current.forEach(releasePreview), []);

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="eyebrow">Photos</span>
        <span className="font-mono text-[11px] text-stone-400">
          {existingCount + files.length}/{MAX_IMAGES}
        </span>
      </div>
      {(files.length > 0) && (
        <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
          {files.map((f, i) => (
            <div key={i} className="relative overflow-hidden rounded-xl border border-stone-200">
              <img src={previewUrl(f)} alt="" className="aspect-square w-full object-cover" />
              <button
                type="button"
                aria-label="Remove photo"
                onClick={() => {
                  releasePreview(f);
                  onRemove(i);
                }}
                className="absolute right-1.5 top-1.5 grid h-6 w-6 place-items-center rounded-full bg-black/60 text-white hover:bg-black/80"
              >
                <XIcon size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      <label
        className={`flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500 transition hover:border-stone-400 hover:bg-stone-100 ${remaining <= 0 ? 'pointer-events-none opacity-40' : ''}`}
      >
        <span className="text-lg leading-none">+</span>
        {files.length === 0 && existingCount === 0 ? 'Add photos of your space (optional)' : `Add more (${remaining} left)`}
        <input
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          disabled={remaining <= 0}
          onChange={(e) => {
            onAdd(Array.from(e.target.files || []).slice(0, remaining));
            e.target.value = '';
          }}
        />
      </label>
      <p className="mt-1.5 font-mono text-[11px] text-stone-400">JPG/PNG, up to {MAX_IMAGES} per listing.</p>
    </div>
  );
}

export default function ListSpace() {
  const { id: editId } = useParams();
  const isEdit = Boolean(editId);
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [files, setFiles] = useState([]);
  const [existingImages, setExistingImages] = useState([]);
  const [loadState, setLoadState] = useState(isEdit ? 'loading' : 'ready');
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [savedId, setSavedId] = useState(null);
  const patch = (p) => setForm((f) => ({ ...f, ...p }));

  const goCancel = () => {
    if (isEdit) {
      // Back to wherever the user came from (usually Profile);
      // fall back to the listing when there is no history (direct URL).
      if (window.history.length > 1) navigate(-1);
      else navigate(`/space/${editId}`, { replace: true });
    } else {
      // The create form lives in its own tab: close it, or go home
      // in-tab when the browser refuses to close.
      closeTabOr(() => navigate('/'));
    }
  };

  useEffect(() => {
    if (!isEdit) return;
    let cancelled = false;
    getSpace(editId)
      .then((space) => {
        if (cancelled) return;
        setForm({
          title: space.title || '',
          description: space.description || '',
          address: space.address || '',
          city: space.city || '',
          state: stateCode(space.state),
          postalCode: space.postalCode || '',
          price: space.price ? String(space.price) : '',
          priceType: space.priceType || 'recurring_per_month',
          availableFrom: space.availableFrom || '',
          availableTo: space.availableTo || '',
        });
        const imgs = space.images?.length ? space.images : space.thumbnailUrl ? [space.thumbnailUrl] : [];
        setExistingImages(imgs);
        setLoadState('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err.status === 404 ? 'Listing not found.' : err.message || 'Could not load listing.');
        setLoadState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [isEdit, editId]);

  const payload = useMemo(() => ({
    title: form.title.trim(),
    description: form.description.trim() || null,
    address: form.address.trim(),
    city: form.city.trim(),
    state: form.state.trim() || null,
    postal_code: form.postalCode.trim(),
    ...(form.latitude != null && form.longitude != null
      ? { latitude: form.latitude, longitude: form.longitude }
      : {}),
    price: Number(form.price) || 0,
    price_type: form.priceType,
    available_from: form.availableFrom,
    available_to: form.availableTo,
  }), [form]);

  const validate = () => {
    if (!payload.title || !payload.address || !payload.city || !payload.postal_code) {
      return 'Title, address, city, and postal code are required.';
    }
    if (!payload.available_from || !payload.available_to) return 'Availability dates are required.';
    if (payload.available_to < payload.available_from) return 'Available-to must be on or after available-from.';
    return '';
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(isEdit ? 'Saving…' : 'Publishing…');
    try {
      const space = isEdit
        ? await updateSpace(editId, payload)
        : await createSpace(payload);
      if (files.length > 0) {
        setBusy('Uploading photos…');
        try {
          await uploadSpaceImages(space.id, files);
        } catch (imgErr) {
          setSavedId(space.id);
          setError(`Saved, but photo upload failed: ${imgErr.message || 'unknown error'}`);
          setBusy('');
          return;
        }
      }
      // Replace the form entry so Back skips it (profile → edit → detail
      // becomes profile → detail instead of looping back into the form).
      navigate(`/space/${space.id}`, { replace: true });
    } catch (err) {
      setError(err.message || (isEdit ? 'Could not save changes.' : 'Could not publish listing.'));
    } finally {
      setBusy((b) => (b === 'Saving…' || b === 'Publishing…' ? '' : b));
    }
  };

  if (loadState === 'loading') {
    return (
      <div className="page !max-w-[760px]">
        <div className="card"><LoadingState label="Loading listing…" /></div>
      </div>
    );
  }
  if (loadState === 'error') {
    return (
      <div className="page !max-w-[760px]">
        <div className="card"><ErrorState message={loadError} /></div>
      </div>
    );
  }

  return (
    <div className="page !max-w-[760px]">
      <div className="card p-6 sm:p-9">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{isEdit ? 'Edit listing' : 'New listing'}</p>
            <h1 className="display mt-1 text-3xl">{isEdit ? 'Edit your space' : 'List your space'}</h1>
            <p className="mt-1.5 text-sm text-stone-500">
              {isEdit ? 'Changes go live immediately.' : 'Free to list. You approve every booking.'}
            </p>
          </div>
          <button type="button" onClick={goCancel} className="text-sm text-stone-400 hover:text-stone-700">Cancel</button>
        </div>

        <form onSubmit={submit} className="mt-7 flex flex-col gap-5">
          <Field label="Listing title">
            <input className="input" value={form.title} onChange={(e) => patch({ title: e.target.value })} placeholder="Walk-in closet near campus" required />
          </Field>
          <Field label="Description">
            <textarea className="input" value={form.description} onChange={(e) => patch({ description: e.target.value })} placeholder="Secure, dry, lockable space a short walk from campus…" />
          </Field>

          {isEdit && existingImages.length > 0 && (
            <div>
              <span className="eyebrow">Current photos</span>
              <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-5">
                {existingImages.map((src, i) => (
                  <img key={i} src={src} alt="" className="aspect-square w-full rounded-xl border border-stone-200 object-cover" />
                ))}
              </div>
            </div>
          )}

          <PhotoPicker
            files={files}
            existingCount={existingImages.length}
            onAdd={(picked) => setFiles((prev) => [...prev, ...picked])}
            onRemove={(i) => setFiles((prev) => prev.filter((_, j) => j !== i))}
          />

          <Field label="Street address" hint="private until booking confirmed">
            <AddressInput
              value={form.address}
              // Typing again drops the coordinates of a picked suggestion: they no longer match.
              onChange={(address) => patch({ address, latitude: null, longitude: null })}
              onSelect={(s) =>
                patch({
                  address: s.address,
                  city: s.city,
                  state: stateCode(s.state),
                  postalCode: s.postalCode,
                  latitude: s.latitude,
                  longitude: s.longitude,
                })
              }
              placeholder="Start typing, e.g. 1842 Euclid Ave"
              required
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-[2fr_1fr_1fr]">
            <Field label="City">
              <input className="input" value={form.city} onChange={(e) => patch({ city: e.target.value })} placeholder="Berkeley" required />
            </Field>
            <Field label="State">
              <select className="input" value={form.state} onChange={(e) => patch({ state: e.target.value })}>
                <option value="">Select…</option>
                {/* A saved value that is not a US state (an old free-text entry) stays selectable. */}
                {form.state && !US_STATES.some((s) => s.value === form.state) && (
                  <option value={form.state}>{form.state}</option>
                )}
                {US_STATES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Postal code">
              <input className="input" value={form.postalCode} onChange={(e) => patch({ postalCode: e.target.value })} placeholder="94709" required />
            </Field>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Price (USD)">
              <input className="input" type="number" min="0" step="0.01" value={form.price} onChange={(e) => patch({ price: e.target.value })} placeholder="45.00" />
            </Field>
            <Field label="Price type">
              <select className="input" value={form.priceType} onChange={(e) => patch({ priceType: e.target.value })}>
                {formPriceTypes.map((o) => (
                  <option key={o.value} value={o.value}>{o.label} — {o.hint}</option>
                ))}
              </select>
            </Field>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Available from">
              <input type="date" className="input" value={form.availableFrom} onChange={(e) => patch({ availableFrom: e.target.value })} required />
            </Field>
            <Field label="Available to">
              <input type="date" className="input" value={form.availableTo} min={form.availableFrom} onChange={(e) => patch({ availableTo: e.target.value })} required />
            </Field>
          </div>

          {error && <p className="text-sm text-red-700">{error}</p>}

          <div className="flex justify-end gap-2">
            <button type="button" onClick={goCancel} className="btn">Cancel</button>
            {savedId ? (
              <button className="btn btn-primary" type="button" onClick={() => navigate(`/space/${savedId}`, { replace: true })}>
                View listing →
              </button>
            ) : (
              <button className="btn btn-primary" type="submit" disabled={!!busy}>
                {busy || (isEdit ? 'Save changes' : 'Publish listing')}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
