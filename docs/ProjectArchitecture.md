## 🏗️ Project Architecture Summary

### Project Outline

1. Problem
   - People have spare space (closets, garages, basements, spare rooms) that sits empty, especially over summer.
   - Storage seekers struggle to find affordable, flexible, nearby storage — commercial units are expensive and require long minimums.
2. Solution
   - A verified, student-focused marketplace for **storage rentals only**.
   - List any unused space for storage of belongings; no housing, subletting, or overnight stays.
3. Target Users
   - People with spare space to rent out for storage
   - Storage seekers: students between semesters, locals needing overflow storage, people between apartments
4. Value Proposition
   - Earn from unused space; store belongings cheaper and closer than commercial storage
   - Safer and more efficient than informal channels
5. Next Steps
   - Validate demand on one campus
   - Build MVP and onboard early users

### App Features

- Post Space
  - Users list unused space (closet, shelf, garage, basement, room) for storage
  - Set dimensions/capacity, dates, price, and access rules
- Find Space
  - Users search for nearby storage
  - Filter by location, dates, price, size, and access type
- Match & Communicate
  - In-app messaging between listers and renters
  - Verified student profiles
- Book
  - Request a booking with clear start and end dates
  - Availability lock via Redis to prevent double-booking
- Manage Rental
  - Drop-off / pickup reminders
  - Reviews after the storage period ends
- Analytics
  - Listing views, booking counts, occupancy rates
  - Admin/owner dashboard with charts

### Tech Stack

| Layer            | Technology                        |
| ---------------- | --------------------------------- |
| Frontend         | React + Vite + React Router       |
| Styling          | Tailwind CSS v4 (`@tailwindcss/vite`) |
| API Framework    | FastAPI + Uvicorn                 |
| Database         | PostgreSQL + asyncpg              |
| Media storage    | SeaweedFS (S3-compatible)         |
| Cache / Sessions | Redis                             |
| Auth             | Google Login + UUID + bcrypt password |
| Payments         | Stripe API (Phase 2)              |
| Real-Time        | WebSockets + Redis Pub/Sub        |
| Maps & Geocoding | OpenStreetMap data: Nominatim geocoding (LocationIQ fallback) + MapLibre GL with the Klokantech Basic style (Geoapify) |
| Analytics (marketing) | Google Analytics (GA4)       |
| Analytics (business)  | Custom Postgres queries + Recharts |
| Testing          | pytest + httpx                    |
| Deployment       | Docker + Nginx + Railway/Render   |

**Frontend styling (Tailwind CSS v4).** The Vite plugin (`@tailwindcss/vite`,
registered in `frontend/vite.config.js`) compiles utilities on demand; `frontend/src/index.css`
starts with `@import "tailwindcss"` followed by the existing Campus Nest design tokens
(`--ink`, `--accent`, `.wire-card`, `.btn`, …). Use Tailwind utilities for layout/spacing in
new JSX and keep the custom `wire-*` / `btn` classes for the neo-brutalist components —
both work together. No `tailwind.config.js` needed (v4 is CSS-first; use `@theme` in CSS
if you need custom tokens).

### Core API Endpoints

**Auth**

- `POST /auth/register` — create account
- `POST /auth/login` — returns JWT tokens
- `POST /auth/logout` — invalidate token in Redis
- `POST /auth/refresh` — issue new access token

**Users**

- `GET /users/me` — get my profile
- `PUT /users/me` — update my profile (name, phone, university, description ≤ 200 words)
- `POST /users/me/avatar` — upload avatar to SeaweedFS
- `GET /users/{id}` — get public profile of another user

**Spaces**

- `POST /spaces` — list a storage space (closet, shelf, garage, basement, room)
- `GET /spaces` — search with filters (cached in Redis)
- `GET /spaces/{id}` — space detail (cached in Redis)
- `PUT /spaces/{id}` — update listing (invalidates cache)
- `DELETE /spaces/{id}` — remove listing
- `POST /spaces/{id}/images` — upload photos

**Bookings**

- `POST /bookings` — book a space (with Redis lock for availability)
- `GET /bookings/me` — my bookings
- `PATCH /bookings/{id}/cancel` — cancel booking

**Messages**

- `WS /ws/{conversation_id}` — real-time chat
- `GET /conversations` — list my conversations
- `GET /conversations/{id}/messages` — message history

**Reviews**

- `POST /reviews` — submit a review
- `GET /spaces/{id}/reviews` — space reviews
- `GET /users/{id}/reviews` — user reviews

**Analytics**

- `GET /analytics/bookings` — booking counts over time
- `GET /analytics/spaces/top` — most viewed/booked spaces
- `GET /analytics/users/growth` — user signup trends
- `GET /analytics/occupancy` — occupancy rates by city/space type

> Marketing analytics (traffic, acquisition, demographics) handled by Google Analytics (GA4) — add the script tag to `index.html`. Business metrics (bookings, occupancy, space performance) served from Postgres and visualized with Recharts on the frontend.

**Maps & Geocoding**

- **Choice: OpenStreetMap data, with a different provider for each job.** Campus Nest is a paid marketplace (Stripe in Phase 2), so treat usage as **commercial** when picking free tiers.
  - **Geocoding (backend) — MVP: public Nominatim.** `GET https://nominatim.openstreetmap.org/search` converts a listing address to lat/long on `POST /spaces/post` and `PUT /spaces/{id}`. Use structured params (`street`, `city`, `postalcode`, `countrycodes`) with `format=jsonv2&limit=1`; an empty result array → `400 GEOCODE_FAILED`. Response `lat`/`lon` are strings — cast to float. Results are stored in Postgres, which is what the Nominatim usage policy asks for.
  - **Geocoding — if the limits are outgrown: LocationIQ.** Its API returns the same Nominatim-style response, so switching is a base-URL + API-key change (free tier: 5,000 requests/day, 2/second, hard cap; free commercial use with a "Search by LocationIQ.com" link). Confirm LocationIQ's terms on storing results long-term before switching.
  - **Reverse geocoding (optional):** `GET {MAP_URL}/reverse?lat=..&lon=..&format=jsonv2` turns coordinates back into an address (e.g., "drop a pin" when posting a space).
  - **Map display (frontend) — MapLibre GL with the Klokantech Basic style, served by Geoapify.** `frontend/src/components/SpaceMap.jsx` renders the map with `maplibre-gl` through `react-map-gl/maplibre`, one price-pill marker per listing that has coordinates, and zooms to fit them. The style is loaded from `https://maps.geoapify.com/v1/styles/klokantech-basic/style.json?apiKey=YOUR_KEY`; the style file carries the required attribution. Geoapify free plan: 3,000 credits/day (about 12,000 tiles, roughly 2,000 vector map views a day), commercial use allowed with attribution, soft limits. Without `VITE_MAP_STYLE_URL` the map falls back to the public `https://tile.openstreetmap.org` raster tiles, which is fine for light development use.
  - **Map display — when daily map views pass the Geoapify quota:** move to **MapTiler** (Flex, ~$25/month) or **Stadia Maps** (Starter, ~$20/month) and point `VITE_MAP_STYLE_URL` at their equivalent style. Their free tiers are **non-commercial only**, so they are for development, not for production on a free plan.
  - **MapLibre version note:** the frontend uses MapLibre GL v6 (older v5 releases have a critical `DOM.sanitize()` XSS advisory). v6 does not bundle its worker, so `SpaceMap.jsx` imports it with Vite's `?worker&url` and calls `setWorkerUrl`.
- **Configuration:** keep every provider URL and key in environment variables so changing provider needs no code changes.
  - Backend (`backend/.env`, read by `backend/config/map_config.py`): `MAP_URL` (geocoder base URL, default public Nominatim), `GEOCODER_API_KEY` (sent as `key`; empty for public Nominatim), `MAP_USER_AGENT` (default `CampusNest/1.0`), `MAP_COUNTRY_CODES` (default `us`).
  - Frontend (`frontend/.env.local`): `VITE_MAP_STYLE_URL`, the complete style.json URL including the API key. Restrict that key to your domains in the Geoapify dashboard, since it is visible in the browser.
  - Provider response formats differ (Geoapify, MapTiler, and Stadia geocoders are not Nominatim-compatible), so geocoding stays behind one backend function, `geocode_address` in `backend/crud/map.py`.
- **Code layout:** `crud/map.py` (geocoder call, Redis cache, rate limit), `routers/map.py` (`GET /api/map/geocode` address preview), `routers/spaces.py` (geocodes on `POST /spaces/post` and on `PUT /spaces/{id}` when the address changes), and `scripts/backfill_geocodes.py` (`python -m scripts.backfill_geocodes`, geocodes older listings that have no coordinates).
- **Usage-policy requirements:**
  - Public Nominatim: max **1 request/second**, send an identifying `User-Agent` (e.g., `CampusNest/1.0 (contact@email)`), cache results, and **no search-as-you-type autocomplete**. Geocode only on create/update, never per search request.
  - Always show map attribution: `© OpenStreetMap contributors`, plus the tile provider's own attribution (Geoapify, MapTiler, Stadia) as its terms require.
  - Self-hosting Nominatim (Docker, one state extract) is an option if autocomplete, bulk geocoding, or privacy becomes a requirement; self-hosting tiles is heavy and not recommended early.
- For privacy, store exact lat/long server-side but only return a **fuzzed/approximate** location (e.g., a circle over the block) to renters until a booking is confirmed.
- Proximity/"near campus" search: store `latitude`/`longitude` on the spaces table and filter with a bounding-box or PostGIS `ST_DWithin` query; campus coordinates can be a small lookup table.
- Alternatives: **Mapbox** (polished vector maps, free tier then usage-based pricing) or **Google Maps Platform** (best autocomplete/geocoding accuracy, highest cost).


**Payments (Phase 2)**

- `POST /payments/create-intent` — initiate Stripe payment
- `POST /payments/webhook` — Stripe callback

---

## 🔑 Redis Key Design

| Key Pattern                      | Value         | TTL       | Purpose                |
| -------------------------------- | ------------- | --------- | ---------------------- |
| `session:{user_id}`              | refresh token | 7 days    | Auth sessions          |
| `blacklist:{token}`              | `1`           | token TTL | Logout blacklist       |
| `space:{id}`                     | JSON          | 10 min    | Space detail cache     |
| `search:{hash}`                  | JSON array    | 5 min     | Search results cache   |
| `lock:booking:{space_id}:{date}` | `1`           | 10 min    | Date availability lock |
| `rate:{ip}:{endpoint}`           | counter       | 60 sec    | Rate limiting          |
| `rating:{space_id}`              | float         | 1 hour    | Cached avg rating      |
