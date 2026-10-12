import { priceTypeMeta } from './data.js';

const TOKEN_KEY = 'campusnest_token';
const USER_KEY = 'campusnest_user';

const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (import.meta.env.DEV ? 'http://127.0.0.1:5001/api' : '/api');

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function readStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function storeUser(user) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

function formatDetail(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || item.message || JSON.stringify(item))
      .join('; ');
  }
  if (typeof detail === 'object') return detail.message || JSON.stringify(detail);
  return String(detail);
}

function buildUrl(path, query) {
  const qs = new URLSearchParams();
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue;
      qs.set(key, String(value));
    }
  }
  const suffix = qs.toString();
  return `${API_BASE}${path}${suffix ? `?${suffix}` : ''}`;
}

// In-flight GETs, keyed by method + URL + auth state. Simultaneous identical
// reads share one network request.
const inflightGets = new Map();

export async function api(path, { method = 'GET', body, query, auth = false } = {}) {  const token = getAuthToken();
  if (auth && !token) throw new ApiError('Please log in', 401);

  const url = buildUrl(path, query);
  // Dedupe simultaneous identical GETs (StrictMode double-effects in dev,
  // plus overlapping context/page fetches). One network request, shared result.
  const key = method === 'GET' ? `GET ${url} ${token ? 'auth' : 'anon'}` : null;
  if (key) {
    const inflight = inflightGets.get(key);
    if (inflight) return inflight;
    const promise = doFetch(url, method, body, token).finally(() => {
      if (inflightGets.get(key) === promise) inflightGets.delete(key);
    });
    inflightGets.set(key, promise);
    return promise;
  }
  return doFetch(url, method, body, token);
}

async function doFetch(url, method, body, token) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const message =
      formatDetail(payload?.detail) ||
      payload?.message ||
      res.statusText ||
      'Request failed';
    throw new ApiError(message, res.status, payload);
  }

  // Backend envelope: { code, message, data }
  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data;
  return payload;
}

async function apiForm(path, { file, field = 'file', files, auth = true } = {}) {
  const token = getAuthToken();
  if (auth && !token) throw new ApiError('Please log in', 401);
  const form = new FormData();
  if (files) files.forEach((f) => form.append('files', f));
  else if (file) form.append(field, file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  const payload = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      formatDetail(payload?.detail) || payload?.message || 'Upload failed',
      res.status,
      payload,
    );
  }
  return payload?.data ?? payload;
}

/* ---------- mappers (tolerate both `id` and `space_id` keys) ---------- */

export function mapSpace(space) {
  if (!space) return null;
  const rawId = space.id ?? space.space_id;
  const priceType = space.price_type ?? space.priceType ?? 'recurring_per_month';
  const meta = priceTypeMeta[priceType] || priceTypeMeta.recurring_per_month;
  const from = space.available_from ?? space.availableFrom ?? '';
  const to = space.available_to ?? space.availableTo ?? '';
  const city = space.city || '';
  return {
    id: String(rawId),
    title: space.title || 'Untitled space',
    description: space.description || '',
    address: space.address || '',
    city,
    postalCode: space.postal_code ?? space.postalCode ?? '',
    price: Number(space.price) || 0,
    priceType,
    priceUnit: meta.unit,
    priceTypeLabel: meta.label,
    availableFrom: from,
    availableTo: to,
    latitude: space.latitude == null ? null : Number(space.latitude),
    longitude: space.longitude == null ? null : Number(space.longitude),
    viewCount: space.view_count ?? space.viewCount ?? 0,
    thumbnailUrl: space.thumbnail_url ?? space.thumbnailUrl ?? null,
    images: space.images ?? [],
    isActive: space.is_active ?? space.isActive ?? true,
    notAccepting: space.not_accepting ?? space.notAccepting ?? false,
    expiredAt: space.expired_at ?? space.expiredAt ?? null,
    ownerId: space.owner_id ?? space.ownerId ?? null,
    createdAt: space.created_at ?? space.createdAt,
    updatedAt: space.updated_at ?? space.updatedAt,
    subtitle: [city, formatDateRange(from, to)].filter(Boolean).join(' · '),
  };
}

export function mapUser(user) {
  if (!user) return null;
  return {
    id: String(user.id),
    email: user.email || '',
    username: user.username || '',
    phone: user.phone || '',
    university: user.university || '',
    description: user.description || '',
    avatarUrl: user.avatar_url ?? user.avatarUrl ?? '',
    isVerified: Boolean(user.is_verified ?? user.isVerified),
    createdAt: user.created_at ?? user.createdAt,
    updatedAt: user.updated_at ?? user.updatedAt,
  };
}

export function mapBooking(b) {
  if (!b) return null;
  return {
    id: String(b.id),
    spaceId: String(b.space_id ?? b.spaceId),
    renterId: b.renter_id ?? b.renterId,
    ownerId: b.owner_id ?? b.ownerId,
    startDate: b.start_date ?? b.startDate,
    endDate: b.end_date ?? b.endDate,
    status: b.status,
    price: Number(b.price) || 0,
    priceType: b.price_type ?? b.priceType,
    totalPrice: Number(b.total_price ?? b.totalPrice) || 0,
    specialDeal: Number(b.special_deal ?? b.specialDeal) || 0,
    cancelRequestedBy: b.cancel_requested_by ?? b.cancelRequestedBy ?? null,
    createdAt: b.created_at ?? b.createdAt,
    updatedAt: b.updated_at ?? b.updatedAt,
  };
}

function unwrapAuth(data) {
  return {
    token: data.token,
    user: mapUser(data.user_info ?? data.userInfo ?? data.user),
  };
}

/* ---------- formatting ---------- */

export function formatDate(iso) {
  if (!iso) return '';
  const value = iso.length === 10 ? `${iso}T00:00:00` : iso;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function formatDateRange(from, to) {
  if (!from && !to) return '';
  if (from === to) return formatDate(from);
  return `${formatDate(from)} – ${formatDate(to)}`;
}

export function formatPrice(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return '0';
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export function initials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function memberSince(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `Member since ${date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}`;
}

export function estimateTotal(price, priceType, start, end) {
  const amount = Number(price) || 0;
  if (!start || !end) return amount;
  const days = Math.round((new Date(end) - new Date(start)) / 86400000);
  if (days <= 0) return amount;
  if (priceType === 'single') return amount;
  if (priceType === 'recurring_per_week') return amount * Math.ceil(days / 7);
  return amount * Math.ceil(days / 30);
}

export function safeNext(value) {
  if (value && value.startsWith('/') && !value.startsWith('//')) return value;
  return '/';
}

/* ---------- auth / users ---------- */

export function login(email, password) {
  return api('/auth/login', { method: 'POST', body: { email, password } }).then(unwrapAuth);
}

export function register(email, password, username) {
  return api('/auth/register', { method: 'POST', body: { email, password, username } }).then(
    unwrapAuth,
  );
}

export async function logout() {
  try {
    await api('/auth/logout', { method: 'POST', auth: true });
  } catch {
    // Clear the local session even if the token is already invalid.
  }
}

export function getMe() {
  return api('/users/me', { auth: true }).then(mapUser);
}

export function getUserProfile(id) {
  return api(`/users/${id}`).then(mapUser);
}

export function updateMe(body) {
  return api('/users/me', { method: 'PUT', auth: true, body }).then(mapUser);
}

export function uploadAvatar(file) {
  return apiForm('/users/me/avatar', { file, field: 'file' }).then(mapUser);
}

/* ---------- spaces (real query aliases: kw, pc, from, to, price-type, min, max, pg, pg-size, sort, order) ---------- */

export async function searchSpaces(filters = {}) {
  const data = await api('/spaces/all', {
    query: {
      kw: filters.keyword,
      city: filters.city,
      pc: filters.postalCode,
      from: filters.availableFrom,
      to: filters.availableTo,
      'price-type': filters.priceType,
      min: filters.minPrice,
      max: filters.maxPrice,
      pg: filters.page ?? 1,
      'pg-size': filters.pageSize ?? 12,
      sort: filters.sortBy,
      order: filters.sortOrder,
      show_non_accepting: filters.showNonAccepting ? true : undefined,
    },
  });
  return {
    total: data?.total_count ?? 0,
    hasMore: Boolean(data?.has_more),
    totalPages: data?.total_pages ?? 0,
    spaces: (data?.spaces ?? []).map(mapSpace),
  };
}

export async function getSpace(id) {
  const data = await api(`/spaces/${id}`);
  const space = mapSpace(data);
  if (space && data?.images?.length && !space.images?.length) space.images = data.images;
  return space;
}

export async function listMySpaces(page = 1, pageSize = 25) {
  const data = await api('/spaces/me', {
    auth: true,
    query: { page, page_size: pageSize },
  });
  return {
    total: data?.total_count ?? 0,
    totalPages: data?.total_pages ?? 0,
    hasMore: Boolean(data?.has_more),
    spaces: (data?.spaces ?? []).map(mapSpace),
  };
}

export async function listOwnerSpaces(ownerId, page = 1, pageSize = 25) {
  const data = await api(`/spaces/from/${ownerId}`, { query: { page, page_size: pageSize } });
  return {
    total: data?.total_count ?? 0,
    totalPages: data?.total_pages ?? 0,
    hasMore: Boolean(data?.has_more),
    spaces: (data?.spaces ?? []).map(mapSpace),
  };
}

export function createSpace(body) {
  return api('/spaces/post', { method: 'POST', auth: true, body }).then(mapSpace);
}

export function updateSpace(id, body) {
  return api(`/spaces/${id}`, { method: 'PUT', auth: true, body }).then(mapSpace);
}

export function deleteSpace(id) {
  return api(`/spaces/${id}`, { method: 'DELETE', auth: true });
}

export function setSpaceAccepting(id, notAccepting) {
  return api(`/spaces/${id}/accepting`, {
    method: 'PATCH',
    auth: true,
    body: { not_accepting: notAccepting },
  }).then(mapSpace);
}

export function renewSpace(id) {
  return api(`/spaces/renew/${id}`, { method: 'PUT', auth: true });
}

export function uploadSpaceImages(id, files) {
  return apiForm(`/spaces/${id}/images`, { files });
}

/* ---------- saved ---------- */

export async function listSaved(page = 1, pageSize = 25) {
  const data = await api('/saved/list', {
    auth: true,
    query: { page, page_size: pageSize },
  });
  const items = (data?.saved_list ?? []).map((row) => ({
    ...mapSpace(row.space),
    savedAt: row.saved_at,
  }));
  return {
    total: data?.total_count ?? items.length,
    hasMore: Boolean(data?.has_more),
    items,
  };
}

export function saveSpace(id) {
  return api(`/saved/${id}`, { method: 'POST', auth: true });
}

export function unsaveSpace(id) {
  return api(`/saved/${id}`, { method: 'DELETE', auth: true });
}

export async function savedStatus(id) {
  const data = await api(`/saved/${id}`, { auth: true });
  return Boolean(data?.saved);
}

/* ---------- history ---------- */

export function recordView(id) {
  return api(`/history/${id}`, { method: 'POST', auth: true });
}

export async function listHistory({ cursor, pageSize = 12 } = {}) {
  const data = await api('/history/list', {
    auth: true,
    query: { cursor, page_size: pageSize },
  });
  return {
    total: data?.total_count ?? 0,
    hasMore: Boolean(data?.has_more),
    nextCursor: data?.next_cursor ?? null,
    items: (data?.history_list ?? []).map((row) => ({
      ...mapSpace(row.space),
      viewedAt: row.viewed_at,
    })),
  };
}

export function deleteHistory(id) {
  return api(`/history/${id}`, { method: 'DELETE', auth: true });
}

export function clearHistory() {
  return api('/history/clear', { method: 'DELETE', auth: true });
}

/* ---------- bookings ---------- */

export function createBooking({ spaceId, startDate, endDate }) {
  return api('/bookings/', {
    method: 'POST',
    auth: true,
    body: { space_id: Number(spaceId), start_date: startDate, end_date: endDate },
  }).then(mapBooking);
}

export async function listBookings({ view = 'renter', status, page = 1, pageSize = 10 } = {}) {
  const data = await api('/bookings/me', {
    auth: true,
    query: { view, status, page, page_size: pageSize },
  });
  return {
    total: data?.total_count ?? 0,
    bookings: (data?.bookings ?? []).map(mapBooking),
  };
}

export function getBooking(id) {
  return api(`/bookings/details/${id}`, { auth: true }).then(mapBooking);
}

export function updateBooking(id, { startDate, endDate }) {
  return api(`/bookings/details/${id}`, {
    method: 'PUT',
    auth: true,
    body: { booking_id: id, start_date: startDate, end_date: endDate },
  });
}

export function cancelBooking(id) {
  return api('/bookings/cancel', { method: 'PATCH', auth: true, body: { booking_id: id } });
}

export function withdrawCancel(id) {
  return api('/bookings/cancel/withdraw', {
    method: 'PATCH',
    auth: true,
    body: { booking_id: id },
  });
}

export function acceptBooking(id) {
  return api('/bookings/accept', { method: 'PATCH', auth: true, body: { booking_id: id } });
}

export function confirmBooking(id) {
  return api('/bookings/confirm', { method: 'PATCH', auth: true, body: { booking_id: id } });
}

export function declineBooking(id) {
  return api('/bookings/decline', { method: 'PATCH', auth: true, body: { booking_id: id } });
}

export function setSpecialDeal(id, price) {
  return api('/bookings/special', {
    method: 'PATCH',
    auth: true,
    body: { booking_id: id, price },
  });
}
