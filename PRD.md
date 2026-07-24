# Product Requirements Document
## Summer Storage Marketplace

**Version:** 2.0  
**Date:** 2026-06-23  
**Status:** Draft

---

## 1. Executive Summary

A two-sided marketplace for **storage only**. College students and locals with spare space — a closet, a shelf, a garage corner, or a whole spare room used purely for storage — list it during summer break, and people who need somewhere to keep their belongings rent that space at flexible durations. The platform gives outgoing students a way to earn from unused space and gives storage seekers an affordable, nearby, verified alternative to commercial self-storage — a gap that commercial storage facilities, Craigslist, and Facebook groups serve poorly.

This platform does **not** handle housing, subletting, or short-term occupancy. No one stays overnight. Listings are for the storage of belongings only.

---

## 2. Problem Statement

### For people with unused space
- Spare rooms, closets, basements, and garages sit empty over summer while leases keep running.
- There's no easy, trusted way to monetize that space for storage.
- Informal arrangements through Facebook groups or Craigslist are unverified and awkward to coordinate.

### For storage seekers
- Commercial storage is expensive (~$150–300/mo for a 5×5 unit) and often far from campus or home.
- Commercial units usually require month-long minimums and rigid contracts.
- Students between semesters or apartments need cheap, short-term, nearby storage — not a long-term commercial lease.

---

## 3. Target Audience

### Primary Users

#### Persona A — The Space Provider (Lister)
- **Who:** Student, graduate, or local resident with spare storage capacity (closet, shelf, garage, basement, spare room)
- **Situation:** Going home for the summer, has extra space year-round, or simply wants to earn from unused square footage
- **Pain point:** Space sits empty; no trusted, simple way to rent it out for storage
- **Goal:** Earn income from unused space with minimal hassle and a trustworthy renter
- **Tech comfort:** High — uses apps daily, expects a smooth mobile experience
- **Decision driver:** Verified renter, clear written agreement, control over access, quick setup

#### Persona B — The Storage Seeker (Renter)
- **Who:** Student staying on campus with too much stuff, a local needing overflow storage, or someone between apartments
- **Situation:** Between apartments, downsizing, studying abroad, or between semesters; needs to store belongings for 2–12 weeks
- **Pain point:** Commercial storage units are expensive, far away, and require month-long minimums
- **Goal:** Rent a shelf, closet, garage corner, or spare room cheaply from someone nearby for exactly the time they need
- **Tech comfort:** High
- **Decision driver:** Price (significantly cheaper than commercial), proximity, ease of access, and verified host

### Secondary Users

#### Persona C — The Platform Admin
- **Who:** Internal team member managing listings and disputes
- **Needs:** Analytics dashboard, user moderation tools, flagged listing review

---

## 4. Goals & Success Metrics

### Phase 1 Goals (MVP — 1 campus, 3 months)
| Goal | Metric | Target |
|------|--------|--------|
| Validate supply | Storage listings created | 50+ in first month |
| Validate demand | Bookings completed | 20+ in first summer |
| User trust | Review completion rate | > 70% of completed bookings |
| Retention signal | Repeat listing or booking | > 20% of users |

### Phase 2 Goals (Multi-campus, 6 months post-launch)
| Goal | Metric | Target |
|------|--------|--------|
| Platform growth | New campus onboarded | 3 campuses |
| Revenue | Booking GMV | $50K/summer |
| Safety | Dispute rate | < 5% of bookings |

---

## 5. User Stories

### Auth & Onboarding
- As a new user, I can register with my email, then verify my `.edu` address to unlock listing creation.
- As a returning user, I can log in with email/password and stay logged in for 7 days.
- As any user, I can upload a profile photo and fill out name, phone, and university.

### Listing (Lister flow)
- As a lister, I can create a storage listing with space type (closet, shelf, garage, basement, room), dimensions or capacity, available dates, price/month, and access rules.
- As a lister, I can specify access hours (e.g., "M–F, 9am–6pm") and whether access is self-serve or host-accompanied.
- As a lister, I can upload up to 10 photos per listing.
- As a lister, I can pause, edit, or delete my listing at any time.
- As a lister, I can see how many people viewed my listing and how many booking requests I received.

### Discovery (Renter flow)
- As a renter, I can search by city or campus, date range, space size, and max price.
- As a renter, I can filter by access type (self-serve vs. host-accompanied) and access hours.
- As a renter, I can view a listing detail page with photos, dimensions, access rules, host profile, and reviews.
- As a renter, I can browse storage listings on a map and see every space within the current map view.
- As a renter, when I pan or zoom the map, results don't reload automatically — a "Search this area" button appears and refreshes results only when I tap it.
- As a renter, I can save listings to a watchlist.

### Booking
- As a renter, I can request a booking with start date, end date, and an intro message to the host.
- As a lister, I can accept or decline a booking request within 24 hours.
- As a renter, I am protected from double-bookings (system holds a lock on the space during a pending request).
- As a renter, I can cancel a booking before a cutoff date defined by the host.

### Messaging
- As either party, I can send and receive real-time messages in a conversation tied to a booking request.
- As either party, I receive a notification (in-app) when I get a new message.

### Reviews
- As a renter, after my storage period ends I can leave a review (rating + text) for the space and host.
- As a lister, after the period ends I can leave a review of the renter.
- As any user, I can view aggregated ratings on profiles and listings.

---

## 6. Feature Requirements

### 6.1 Functional Requirements

#### Auth
- Google login api
- UUID access tokens (15 min TTL) + refresh tokens (7 days, stored in Redis)
- Rate limiting on login endpoint (5 attempts / 60s per IP) Phase 2

#### User Profiles
- Avatar upload (stored in SeaweedFS)
- Editable display name, phone, university, bio
- Public profile shows listings, reviews, and member-since date

#### Listings
- Required fields: title, space type, address (city + zip minimum), dimensions or capacity, price, currency, available_from, available_to
- Up to 10 images per listing, stored in SeaweedFS
- Payment type
- Auto expired in 1 months max (others can't see it), can be renewed. Auto delete in 3 months 

#### Search & Discovery
- Filter by: space type, city, date range, max_price, min_price, size/capacity, access type
- Search results cached in Redis (5 min TTL, invalidated on listing update)
- Listing detail cached in Redis (10 min TTL)
- Results sorted by relevance (date match quality) then by price

#### Map View (Zillow-style)
- Map renders storage listings as price-pill markers using Mapbox GL JS; results stay in sync with a side list panel.
- **Viewport-driven search:** the map queries listings whose `latitude`/`longitude` fall within the current visible bounds (bounding box). Served by a lean `GET /spaces/map?bbox=w,s,e,n&...filters` endpoint returning GeoJSON plus a total count.
- **Manual refresh (no auto-reload):** panning or zooming does *not* refetch. Instead, once the view drifts beyond a threshold, a floating "Search this area" button appears; results refresh only when the user taps it. Initial load and filter changes still query immediately for the current bounds.
- **Clustering:** nearby pins group into count bubbles at low zoom (Mapbox built-in clustering for MVP; server-side grid aggregation at scale).
- **Privacy:** markers use a fuzzed/approximate location computed on the fly from exact coordinates; the precise address is never exposed until a booking is confirmed.
- **Performance:** marker results capped (~200–300) with the true total surfaced separately; bbox responses cached in Redis under a rounded-bounds key (short TTL).

#### Bookings
- States: `pending` → `confirmed` → `active` → `completed` | `cancelled` | `declined`
- Redis availability lock held during pending state (10 min TTL auto-expires)
- Cancel policy set per listing: `flexible` (48h before), `moderate` (5 days before), `strict` (no refund)
- Booking confirmation email (Phase 2: Stripe payment confirmation)

#### Messaging
- WebSocket connections per conversation
- Redis Pub/Sub fan-out for multi-device support
- Message history persisted in PostgreSQL
- Conversations auto-created when a booking request is sent

#### Reviews
- One review per completed booking per direction (renter → listing, lister → renter)
- Rating: 1–5 stars
- Review visible only after both parties submit OR 14 days after the storage period ends (whichever first)
- Average rating cached in Redis (1 hour TTL)

#### Analytics (Admin)
- Booking counts over time
- Top-viewed and top-booked spaces
- User signup growth curve
- Occupancy rates by city and space type

### 6.2 Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| API response time (p95) | < 300ms for cached reads |
| Availability | 99.5% uptime during peak (May–August) |
| Concurrent WebSocket connections | Support 500 simultaneous |
| Image upload size limit | 10 MB per image |
| Data retention | Messages retained 2 years; listings 5 years |
| Auth security | bcrypt cost factor ≥ 12; HTTPS only |
| GDPR/CCPA | Account deletion clears PII within 30 days |

---

## 7. Out of Scope (MVP)

- **Housing / subletting / overnight stays** — the platform is for storage of belongings only and will not support occupancy
- **Payments** — handled in Phase 2 via Stripe; MVP uses off-platform payment with trust/reviews as safeguard
- **Identity verification** — no government ID checks in MVP; `.edu` email is the trust signal
- **Insurance / liability coverage for stored items** — not offered in MVP; renters store at their own risk
- **Mobile native app** — MVP is web-responsive only
- **Multi-currency** — USD only for MVP
- **Push notifications** — in-app only for MVP; email in Phase 1.5
- **Map view** — list view only for MVP; the Zillow-style map view (see §6.1 Map View) ships in Phase 2
- **Item pickup/delivery / moving service** — renters arrange their own transport

---

## 8. Phases & Milestones

### Phase 1 — MVP (weeks 5–14) 

* Craiglist style: no direct message in app

- Auth, user profiles, storage listings, search, basic booking flow (no payments)
- Reviews after a storage period completes
- Zillow-style map view with viewport search and "Search this area" button (Mapbox GL JS)
- Deploy on Railway/Render behind Nginx

### Phase 2 — Trust & Notifications (weeks 15–18)
- Rate limiting
- Transactional email (booking confirmed, new message, review reminder)
- Lister analytics (views, booking count)
- In-app messaging via WebSockets

### Phase 3 — Payments & Scale (weeks 19–26)
- Stripe payment on booking confirmation
- Paid promotion listing service
- Stripe webhook for payout to lister
- Multi-campus expansion
- Admin analytics dashboard with Recharts

---

## 9. Risks & Open Questions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Low supply at launch (no listings = no renters) | High | High | Seed manually via campus boards; offer lister incentives |
| Liability if stored items are damaged, lost, or stolen | Medium | High | Add disclaimer; renters store at own risk in MVP; explore item insurance in Phase 2 |
| Listers storing prohibited items (hazardous, illegal) | Medium | High | Prohibited-items policy in terms; reporting/flagging flow |
| Double-booking race condition | Low | High | Redis lock per space during pending state |
| Seasonal demand drop (Sept–April) | High | Medium | Pivot messaging to semester-break and between-apartment storage |

### Open Questions
1. Do we require `.edu` verification to **list**, or just to receive a verified badge?
2. What is the platform fee model — flat fee, percentage of booking, or freemium?
3. Should storage listings default to self-access (24/7 key) or host-accompanied access only?
4. Which single campus do we target first, and who is our campus ambassador?
5. What categories of items should be prohibited from storage (hazardous, perishable, illegal, high-value)?

---

## 10. Appendix

### Glossary
| Term | Definition |
|------|------------|
| Lister | A user who posts spare space (closet, shelf, garage, basement, or room) for storage |
| Renter / Storage seeker | A user who books a listed space to store their belongings |
| Availability lock | A Redis key that prevents a space from receiving a second booking request while one is pending |
| Access type | Whether the renter can access stored items self-serve or only when accompanied by the host |

### Related Documents
- [ProjectArchitecture.md](./ProjectArchitecture.md) — tech stack, API endpoints, Redis key design
