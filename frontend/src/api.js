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

export async function api(path, { method = 'GET', body, query, auth = false } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const token = getAuthToken();
  if (auth && !token) throw new ApiError('Please log in', 401);
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(buildUrl(path, query), {
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

  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data;
  return payload;
}

export function mapSpace(space) {
  if (!space) return null;
  const priceType = space.price_type ?? space.priceType;
  const meta = priceTypeMeta[priceType] || priceTypeMeta.recurring_per_month;
  const from = space.available_from ?? space.availableFrom ?? '';
  const to = space.available_to ?? space.availableTo ?? '';
  const city = space.city || '';
  return {
    id: String(space.id ?? space.space_id),
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
    createdAt: space.created_at ?? space.createdAt,
    updatedAt: space.updated_at ?? space.updatedAt,
    typeLabel: city || 'Storage',
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

function unwrapAuth(data) {
  return {
    token: data.token,
    user: mapUser(data.user_info ?? data.userInfo ?? data.user),
  };
}

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

export function updateMe(body) {
  return api('/users/me', { method: 'PUT', auth: true, body }).then(mapUser);
}

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
      'pg-size': filters.pageSize ?? 25,
      sort: filters.sortBy,
      order: filters.sortOrder,
    },
  });
  return {
    total: data?.total_count ?? 0,
    hasMore: Boolean(data?.has_more),
    totalPages: data?.total_pages ?? 0,
    spaces: (data?.spaces ?? []).map(mapSpace),
  };
}

export function getSpace(id) {
  return api(`/spaces/${id}`).then(mapSpace);
}

export async function listMySpaces(page = 1, pageSize = 25) {
  const data = await api('/spaces/mine', {
    auth: true,
    query: { page, page_size: pageSize },
  });
  return {
    total: data?.total_count ?? 0,
    hasMore: Boolean(data?.has_more),
    spaces: (data?.spaces ?? []).map(mapSpace),
  };
}

export function createSpace(body) {
  return api('/spaces/post', { method: 'POST', auth: true, body }).then(mapSpace);
}

export async function listSaved(page = 1, pageSize = 100) {
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

export function recordView(id) {
  return api(`/history/${id}`, { method: 'POST', auth: true });
}

export function createBooking({ spaceId, startDate, endDate }) {
  return api('/bookings/', {
    method: 'POST',
    auth: true,
    body: { space_id: spaceId, start_date: startDate, end_date: endDate },
  });
}
