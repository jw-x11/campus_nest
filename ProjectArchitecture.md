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
| API Framework    | FastAPI + Uvicorn                 |
| Database         | PostgreSQL + asyncpg              |
| Media storage    | SeaweedFS (S3-compatible)         |
| Cache / Sessions | Redis                             |
| Auth             | Google Login + UUID + bcrypt password |
| Payments         | Stripe API (Phase 2)              |
| Real-Time        | WebSockets + Redis Pub/Sub        |
| Maps & Geocoding | Mapbox (GL JS + Geocoding API)    |
| Analytics (marketing) | Google Analytics (GA4)       |
| Analytics (business)  | Custom Postgres queries + Recharts |
| Testing          | pytest + httpx                    |
| Deployment       | Docker + Nginx + Railway/Render   |

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

- **Recommendation: Mapbox** — use the Geocoding API to convert listing addresses to lat/long on `POST /spaces`, and Mapbox GL JS for the map view (Phase 2; list view only for MVP). Chosen for generous free tier (~100K loads/mo), low cost at scale, and easy approximate-location rendering.
- For privacy, store exact lat/long server-side but only return a **fuzzed/approximate** location (e.g., a circle over the block) to renters until a booking is confirmed.
- Proximity/"near campus" search: store `latitude`/`longitude` on the spaces table and filter with a bounding-box or PostGIS `ST_DWithin` query; campus coordinates can be a small lookup table.
- Alternatives: **Google Maps Platform** (best autocomplete/geocoding accuracy, higher cost) or **Leaflet + OpenStreetMap/Nominatim** (fully free, but rate-limited geocoding and self-hosting recommended for production).

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
