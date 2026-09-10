# API Endpoint Documentation — Summer Storage Marketplace

**Base URL:** `/api`
**Auth scheme:** `Authorization: Bearer <access_token>` (opaque UUID access token, 15 min TTL)
**Content type:** `application/json` unless a `multipart/form-data` upload is noted.
**Interactive docs:** FastAPI Swagger at `/docs` — test every route here before wiring the frontend.

This document lists endpoints in **the order you should implement them** (from `notes.md`
build order). Each phase builds on the previous one, so complete and test a phase in
Swagger before moving on.

---

## Conventions

### Standard error envelope
All errors return this shape (implement once in `utils/exception_handler.py` and register it
in `main.py`):

```json
{
  "detail": "Human-readable message",
  "code": "Error Code"
}
```

### Common status codes
| Code | Meaning |
|---|---|
| `200 OK` | Successful read/update |
| `201 Created` | Resource created |
| `204 No Content` | Successful delete, no body |
| `400 Bad Request` | Validation/business-rule failure |
| `401 Unauthorized` | Missing/invalid/expired access token |
| `403 Forbidden` | Authenticated but not allowed (e.g. not the owner) |
| `404 Not Found` | Resource does not exist |
| `409 Conflict` | State conflict (e.g. double-booking, duplicate email) |
| `422 Unprocessable Entity` | FastAPI/Pydantic schema validation error |

### Auth column legend
- **Auth: none** — public, no token required.
- **Auth: required** — valid access token required (`get_current_user` dependency).
- **Auth: owner** — valid token *and* the caller must own the resource.

> **Spec note — token type.** The PRD (§6.1) specifies **opaque UUID access tokens + Redis
> refresh tokens**, while `ProjectArchitecture.md` says "JWT". This doc follows the PRD (UUID
> tokens stored/blacklisted in Redis). Pick one and keep `routers/deps.py` consistent with it.

---

# Phase 1 — MVP

## 1. Auth  (`/api/auth`)

Implement first: nothing else can be protected until this exists. Router file:
`backend/routers/auth.py`.

### 1.1 `POST /auth/register`
Create a new account.

- **Auth:** none
- **Request**
```json
{
  "email": "student@university.edu",
  "password": "min-8-chars",
  "username": "Jane Doe"
}
```
- **Response `201`** — the created user profile (see `UserResponse` in §2).
- **Logic**
  - Validate email format (`EmailStr`) and password length.
  - Reject if email already exists → `409 EMAIL_TAKEN`.
  - Hash password with **bcrypt (cost ≥ 12)**, insert into `users`.
  - `is_verified` starts `false`.
- **Errors:** `409` duplicate email, `422` bad payload.

### 1.2 `POST /auth/login`
Authenticate and issue tokens.

- **Auth:** none
- **Request**
```json
{ "email": "student@university.edu", "password": "..." }
```
- **Response `200`**
```json
{
  "access_token": "uuid-string",
  "refresh_token": "uuid-string",
  "token_type": "bearer",
  "expires_in": 900
}
```
- **Logic**
  - Look up user by email; verify bcrypt hash.
  - Generate UUID access token (15 min) and refresh token (7 days).
  - Store `session:{user_id}` → refresh token in Redis (TTL 7 days).
- **Errors:** `401 INVALID_CREDENTIALS`.
- **Phase 2:** rate-limit to 5 attempts / 60s per IP (`rate:{ip}:login`).

### 1.3 `POST /auth/refresh`
Exchange a valid refresh token for a new access token.

- **Auth:** none (refresh token in body)
- **Request**
```json
{ "refresh_token": "uuid-string" }
```
- **Response `200`** — same shape as login.
- **Logic:** validate refresh token against `session:{user_id}` in Redis; issue a new access
  token. Rotate the refresh token if desired.
- **Errors:** `401 INVALID_REFRESH_TOKEN` (expired/unknown).

### 1.4 `POST /auth/logout`
Invalidate the current access token.

- **Auth:** required
- **Request:** empty body (token from `Authorization` header).
- **Response `204`**
- **Logic:** add token to `blacklist:{token}` in Redis (TTL = remaining token TTL); delete
  `session:{user_id}`.

> **Phase 2 — Google Login.** PRD lists Google OAuth. Add `POST /auth/google` (exchange Google
> ID token → platform tokens) when you get there; not required for MVP.

---

## 2. User Profile  (`/api/users`)

Router file: `backend/routers/users.py` (already scaffolded).

### Shared schema — `UserResponse`
```json
{
  "id": "uuid",
  "email": "student@university.edu",
  "username": "Jane Doe",
  "phone": "+1...",
  "university": "State U",
  "description": "Junior with a dry basement closet two blocks from campus.",
  "is_verified": true,
  "avatar_url": "https://seaweedfs/.../avatar.jpg"
}
```

### 2.1 `GET /users/me`
Get the authenticated user's full profile.

- **Auth:** required
- **Response `200`:** `UserResponse`
- **Errors:** `401`.

### 2.2 `PUT /users/me`
Update editable fields.

- **Auth:** required
- **Request** (all optional)
```json
{ "username": "New Name", "phone": "+1...", "university": "State U", "description": "..." }
```
- **Response `200`:** updated `UserResponse`.
- **Logic:** email is **not** editable here (needs separate verification flow). `description`
  is optional, max **200 words**. Update `updated_at`.

### 2.3 `POST /users/me/avatar`
Upload/replace avatar.

- **Auth:** required
- **Request:** `multipart/form-data` with `file` (image, ≤ 10 MB).
- **Response `200`:** updated `UserResponse` with new `avatar_url`.
- **Logic:** upload to SeaweedFS, save returned URL to `users.avatar_url`, delete old object.
- **Errors:** `400 FILE_TOO_LARGE` / `UNSUPPORTED_MEDIA_TYPE`.

### 2.4 `GET /users/{id}`
Public profile of any user.

- **Auth:** none
- **Response `200`:** public subset of `UserResponse` (omit `email`/`phone` if you want them
  private — recommended). Used on listing pages to show lister info.
- **Errors:** `404 USER_NOT_FOUND`.

---

## 3. Spaces  (`/api/spaces`)

The core listing CRUD + search + images. Router file: `backend/routers/spaces.py`.

> **Spec note — space `type`.** DB index `idx_spaces_city_type` references a `type` column and
> the code uses `Literal["room","apartment","storage"]`, but the `spaces` table in
> `DatabaseSchema.md` has no `type` column and the PRD defines types as
> **`closet | shelf | garage | basement | room`**. **Action:** add a `type` column
> (Postgres enum or text) to `spaces` and use the PRD value set. This doc uses the PRD set.
>
> **Spec note — price.** DB defines `price` + `price_type` enum
> (`single | recurring_per_month | recurring_per_week`). Prefer these over the code's
> `price_per_month`. Fields below follow the DB schema.

### Shared schema — `SpaceResponse`
```json
{
  "id": 1,
  "owner_id": "uuid",
  "type": "garage",
  "title": "Dry garage corner near campus",
  "description": "...",
  "city": "Springfield",
  "postal_code": "12345",
  "approx_location": { "lat": 40.12, "lng": -74.5 },
  "price": 60.00,
  "price_type": "recurring_per_month",
  "available_from": "2026-06-01",
  "available_to": "2026-08-15",
  "is_active": true,
  "expired_at": "2026-07-22T00:00:00Z",
  "view_count": 142,
  "is_saved": false,
  "images": ["https://seaweedfs/.../1.jpg"],
  "avg_rating": 4.6
}
```
> **Privacy:** never return exact `address`, `latitude`, or `longitude` to non-confirmed
> renters. Return only `city`, `postal_code`, and a **fuzzed** `approx_location` (snapped to
> the block, computed on the fly). Exact address is revealed only after a booking is confirmed.

### 3.1 `POST /spaces/post`
Create a listing.

- **Auth:** required
- **Request — `SpaceRequest`**
```json
{
  "type": "garage",
  "title": "Dry garage corner near campus",
  "description": "6ft x 4ft, dry, self-serve access M-F 9-6",
  "address": "123 Main St",
  "city": "Springfield",
  "postal_code": "12345",
  "price": 60.00,
  "price_type": "recurring_per_month",
  "available_from": "2026-06-01",
  "available_to": "2026-08-15"
}
```
- **Response `201`:** `SpaceResponse` (`owner_id` = caller).
- **Logic**
  - Geocode `address` via **Mapbox Geocoding API** → store exact `latitude`/`longitude`
    server-side (never returned).
  - `is_active` = true; set `expired_at` = now + 1 month (auto-hidden after, renewable; auto
    delete at 3 months).
- **Errors:** `400 GEOCODE_FAILED`, `422` validation (e.g. `available_to < available_from`).

### 3.2 `GET /spaces/all`
Search/list with filters. **Cached in Redis.**

- **Auth:** none
- **Query params**
  | Param | Type | Notes |
  |---|---|---|
  | `city` | string | exact/indexed match |
  | `type` | enum | space type filter |
  | `available_from` | date | overlap with listing window |
  | `available_to` | date | overlap with listing window |
  | `min_price` | float | |
  | `max_price` | float | |
  | `price_type` | enum | |
  | `page` | int | default 1 |
  | `page_size` | int | default 20, cap 100 |
- **Response `200`**
```json
{ "results": [ /* SpaceInfoResponse[] */ ], "total": 137, "page": 1, "page_size": 20 }
```
- **Logic**
  - Only return `is_active = true` AND `expired_at > now()`.
  - Sort by **relevance (date-match quality) then price**.
  - Cache: hash the normalized query → `search:{hash}` (TTL 5 min). Invalidate on any listing
    create/update/delete.
- **Errors:** `422` invalid filters.

### 3.3 `GET /spaces/{id}`
Listing detail. **Cached in Redis.**

- **Auth:** none
- **Response `200`:** `SpaceResponse` (+ `images`, `avg_rating`; optionally owner summary).
- **Logic:** read-through cache `space:{id}` (TTL 10 min). Still fuzz location. If the
  caller is authenticated, record the view via the same write path as `POST /history/{space_id}`
  (§5.1) so `view_history` and `spaces.view_count` stay in sync. If this GET is served
  entirely from cache, the client should still call `POST /history/{space_id}`. Optionally
  include `is_saved` when a token is present (§4.4).
- **Errors:** `404 SPACE_NOT_FOUND`.

### 3.4 `PUT /spaces/{id}`
Update a listing.

- **Auth:** owner
- **Request:** `SpaceRequest` (full or partial — pick one and be consistent).
- **Response `200`:** updated `SpaceResponse`.
- **Logic:** verify `owner_id == caller` → else `403`. Re-geocode if address changed.
  **Invalidate** `space:{id}` and any `search:*` caches.
- **Errors:** `403 NOT_OWNER`, `404`.

### 3.5 `DELETE /spaces/{id}`
Remove a listing.

- **Auth:** owner
- **Response `204`**
- **Logic:** verify ownership; delete (or soft-delete via `is_active=false`). Cascade-delete
  `space_images`. Invalidate caches.
- **Errors:** `403`, `404`.

### 3.6 `POST /spaces/{id}/images`
Upload photos (up to 10 per listing).

- **Auth:** owner
- **Request:** `multipart/form-data` with `files` (1..N images, ≤ 10 MB each).
- **Response `201`**
```json
{ "images": ["https://seaweedfs/.../1.jpg", "..."] }
```
- **Logic:** verify ownership; upload each to SeaweedFS; insert rows into `space_images` with
  incrementing `sort_order`. Enforce the 10-image cap → `400 IMAGE_LIMIT_REACHED`.
- **Errors:** `400`, `403`, `404`.

> **Phase 2 — Map view.** `GET /spaces/map?bbox=w,s,e,n&<filters>` returns GeoJSON of listings
> within the bounding box + a true total count, capped at ~200–300 markers with fuzzed
> coordinates. Cache under a rounded-bounds key (short TTL). Ships with the Zillow-style map
> ("Search this area" button); not required for MVP list view.
>
> **Saved / views.** When the caller is authenticated, include `is_saved` on `SpaceResponse`
> (and on each card in `GET /spaces/all`) via an `EXISTS` on `saved_spaces` — see §4.4.
> Recording a view is §5 (`POST /history/{space_id}`), not a field on this router.

---

## 4. Saved Spaces  (`/api/saved`)

Watchlist / heart-toggle. Router file: `backend/routers/saved_space.py`.
This is a **user collection**, not listing CRUD — do not put these on `/api/spaces`.

Table: `saved_spaces` (composite PK `(user_id, space_id)`). There is no `saved_count` on
`spaces` — totals are `COUNT(*)` on this table.

### Shared schema — `SavedSpaceItem`
A listing card plus when the caller saved it. Reuse the public `SpaceResponse` fields from §3
(fuzzed location; omit exact address).

```json
{
  "space": { /* SpaceResponse */ },
  "saved_at": "2026-07-22T10:00:00Z"
}
```

### 4.1 `GET /saved/list`
The caller's saved list, newest first.

- **Auth:** required
- **Query**
  | Param | Type | Notes |
  |---|---|---|
  | `page` | int | default 1 |
  | `page_size` | int | default 25, cap 100 |
- **Response `200`**
```json
{
  "results": [ /* SavedSpaceItem[] */ ],
  "total": 12,
  "page": 1,
  "page_size": 25
}
```
- **Logic:** `saved_spaces` for `user_id = caller`, join `spaces`, order by
  `saved_spaces.created_at DESC`. Skip inactive/expired listings or include them with
  `is_active: false` so the UI can show "no longer available" — pick one and stay consistent.
- **Errors:** `401`.

### 4.2 `POST /saved/{space_id}`
Save (favorite) a listing. Idempotent.

- **Auth:** required
- **Response `201`:** `SavedSpaceItem` if a new row was inserted; **`200`** if it was already
  saved (same body). Either is fine as long as the client treats both as "now saved".
- **Logic**
  - `404 SPACE_NOT_FOUND` if the space does not exist or is inactive.
  - `INSERT INTO saved_spaces (user_id, space_id) ... ON CONFLICT (user_id, space_id) DO NOTHING`.
  - Caller should not be able to "save" their own listing if you want that rule → `400`.
- **Errors:** `401`, `404`.

### 4.3 `DELETE /saved/{space_id}`
Unsave a listing. Idempotent.

- **Auth:** required
- **Response `204`**
- **Logic:** `DELETE FROM saved_spaces WHERE user_id = caller AND space_id = :id`. If no
  row existed, still return `204` (second tap / stale UI).
- **Errors:** `401`. (`404` only if you want "was not saved" to be visible; not required.)

### 4.4 `GET /saved/{space_id}`
Whether the caller has saved this listing. Used to initialize the heart without downloading
the full watchlist.

- **Auth:** required
- **Response `200`**
```json
{ "space_id": 1, "saved": true }
```
- **Errors:** `401`. Always `200` with `saved: false` if there is no row (do not 404).

> **Not in this router.** A listing-wide save total is `COUNT(*)` from `saved_spaces` (optional
> on `SpaceResponse`). Per-user `is_saved` on listing payloads (when a token is present) is an
> `EXISTS` on this table, not a separate write API.

---

## 5. View History  (`/api/history`)

Recently viewed listings. Router file: create `backend/routers/view_history.py`.
One row per `(user_id, space_id)`; a re-view updates `viewed_at` instead of inserting again.

Tables: `view_history`, denormalized `spaces.view_count` (total views, **including re-views**).

Anonymous (logged-out) browsing is **not** stored. `GET /spaces/{id}` may call the same write
path when the caller is authenticated; `POST /history/{space_id}` exists so a cache hit on
the listing does not skip the write, and so the client can record a view without refetching.

### Shared schema — `ViewHistoryItem`
```json
{
  "space": { /* SpaceResponse */ },
  "viewed_at": "2026-07-22T10:00:00Z"
}
```

### 5.1 `POST /history/{space_id}`
Record that the caller viewed this listing.

- **Auth:** required
- **Response `200`:** `ViewHistoryItem` (or empty `200` if you do not need the body).
- **Logic**
  - `404 SPACE_NOT_FOUND` if the space does not exist.
  - `INSERT ... ON CONFLICT (user_id, space_id) DO UPDATE SET viewed_at = now()`.
  - **Always** increment `spaces.view_count` (re-views count). Same transaction as the upsert.
  - Optional: skip increment if the last view was within N seconds (debounce refresh spam).
- **Errors:** `401`, `404`.

### 5.2 `GET /history/list`
The caller's recently viewed list, newest first.

- **Auth:** required
- **Query:** `page`, `page_size` (same defaults as `/saved`).
- **Response `200`**
```json
{
  "results": [ /* ViewHistoryItem[] */ ],
  "total": 8,
  "page": 1,
  "page_size": 25
}
```
- **Logic:** `view_history` for `user_id = caller`, join `spaces`, order by `viewed_at DESC`
  (`idx_view_history_user_time`). Inactive listings: same choice as `/saved` (hide vs show
  as unavailable).
- **Errors:** `401`.

### 5.3 `DELETE /history/{space_id}`
Remove one listing from the caller's history.

- **Auth:** required
- **Response `204`**
- **Logic:** delete the `(caller, space_id)` row. **Do not** decrement `spaces.view_count`
  (that is a lifetime total, not "currently in someone's history").
- **Errors:** `401`. Idempotent if the row is already gone.

### 5.4 `DELETE /history/clear`
Clear the caller's entire history.

- **Auth:** required
- **Response `204`**
- **Logic:** `DELETE FROM view_history WHERE user_id = caller`. Do not touch `view_count`.

---

## 6. Bookings  (`/api/bookings`)

Router file: `backend/routers/bookings.py`.
**States:** `pending` → `accepted` → `confirmed` → `active` → `completed`, plus terminals `cancelled` | `declined`.
DB enum: `pending | accepted | confirmed | active | cancelled | completed | declined`.
A nightly job writes `confirmed → active` when `start_date` begins and `active → completed` when `end_date` has passed. Unpaid `accepted` cancels instead of becoming `active`.

### Shared schema — `BookingResponse`
```json
{
  "id": "uuid",
  "space_id": 1,
  "renter_id": "uuid",
  "owner_id": "uuid",
  "start_date": "2026-06-05",
  "end_date": "2026-08-05",
  "status": "pending",
  "price": 15.0,
  "price_type": "recurring_per_month",
  "total_price": 60.00,
  "special_deal": 0.00,
  "cancel_requested_by": null
}
```
`cancel_requested_by` is `null`, `"renter"`, or `"owner"`. `null` means no pending cancel; a role means that party has requested cancel and is waiting on the other.

### 6.1 `POST /bookings`
Request for a booking (with Redis availability lock to prevent double-booking).

- **Auth:** required
- **Request Body**
```json
{ "space_id": 1, "start_date": "2026-06-05", "end_date": "2026-07-05" }
```
- **Response `201`:** `BookingResponse` (status `pending`).
- **Logic**
  1. Validate dates within the space's `available_from`/`available_to` and `end > start`.
  2. Acquire Redis lock `lock:booking:{space_id}:{date}` (TTL 10 min) for the range — use
     `SET NX`. If any date is locked or already booked → `409 SPACE_UNAVAILABLE`.
  3. Insert booking (`pending`); snapshot `owner_id` from the listing; compute `total_price` from `price`/`price_type` × duration.
  4. Release/rely on lock TTL once persisted.
  5. Renter request booking: `pending`
  6. Owner accept / decline: `accepted` / `declined`
  7. Payment succeeded (Stripe or owner in-person receipt): `confirmed`
  8. First day of the stay: `active` (nightly job, or same write as payment if `start_date` is already today)
  9. After rent ended: `completed`
- **Errors:** `400` bad dates, `404` space, `409` unavailable/double-book.

### 6.2 `GET /bookings/me`
List the caller's bookings.

- **Auth:** required
- **Query (optional):** `status`, `view` (`renter` | `owner`, default `renter`), pagination.
- **Response `200`:** `BookingResponse[]`. `view=renter` filters `renter_id == caller`; `view=owner` filters `owner_id == caller`.

### 6.3 `PATCH /bookings/cancel`
Cancel a booking.

- **Auth:** owner (renter who made it, or lister of the space)

- **Request Body**

  * ```json
    {"space_id": 1}
    ```

- **Response `200`:** `BookingResponse`. Status is `cancelled` when cancel takes effect; otherwise status is unchanged and `cancel_requested_by` is the caller's role.
- **Logic**
  1. Caller must be the renter or the listing owner.
  2. `pending` or `accepted`: set `status = cancelled` immediately (one party is enough; payment has not happened).
  3. `confirmed` or `active`: both parties must agree.
     - If `cancel_requested_by` is `null`, set it to the caller's role (`renter` or `owner`) and leave status unchanged.
     - If it is already the other party, set `status = cancelled`.
     - If it is already this party, no-op (still waiting).
  4. `cancelled`, `declined`, or `completed`: `400`.

### 6.4 `PATCH /bookings/accept`

* **Auth**: owner

* **Request Body**

  * ```json
    {"space_id": 1}
    ```

* **Logic**: owner accept the booking request: mark booking as `accepted`. Dates are held; other users cannot book the same range. Payment has not happened yet.

### 6.5 `PATCH /bookings/decline`

* **Auth**: owner

* **Request Body**

  * ```json
    {"space_id": 1}
    ```

* **Logic**: owner declines the booking request: mark booking as `declined`. 

### 6.6 `PATCH /booking/special`

* **Auth**: Owner

* **Request Body**

  * ```json
    {"space_id": 1, "price":"int"}
    ```

* **Logic**: Owner offer a special deal (flat price) for user after negotiating. Over write the original price. Minimum 0.01

### 6.7 `GET /booking/details/{booking_id}`

* **Auth:** Owner or renter
* **Path param**: `booking_id`
* **Reponse**: booking details

### 6.8 `PUT /booking/details/{booking_id} `

* **Auth:** renter

* **Body:** BookingUpdateRequest

  * ```python
    {
        "booking_id": UUID,
        "start_date": date,
        "end_date": date
    }
    ```

* Logic: Update booking dates for renter

* **Response**: Booking details

---

## 7. Messages  (`/api/conversations`, `/api/ws`)

> **Phase note:** PRD §8 says MVP Phase 1 is **Craigslist-style (no in-app messaging)** and
> WebSocket chat lands in **Phase 2**. Build the REST history endpoints first; add the
> WebSocket last. Conversations are auto-created when a booking request is sent.

### Shared schemas
```json
// ConversationResponse
{
  "id": "uuid",
  "space_id": 1,
  "lister_id": "uuid",
  "renter_id": "uuid",
  "updated_at": "2026-07-22T10:00:00Z",
  "last_message": "See you at drop-off"
}

// MessageResponse
{
  "id": "uuid",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "content": "Hi, is the garage still available?",
  "created_at": "2026-07-22T10:00:00Z"
}
```

### 7.1 `GET /conversations`
List the caller's conversations.

- **Auth:** required
- **Response `200`:** `ConversationResponse[]` where caller is `lister_id` or `renter_id`,
  sorted by `updated_at` desc.

### 7.2 `GET /conversations/{id}/messages`
Message history (paginated).

- **Auth:** participant only
- **Query:** `before` (cursor timestamp/id), `limit` (default 50).
- **Response `200`:** `MessageResponse[]` ordered by `created_at` (uses
  `idx_messages_convo`).
- **Errors:** `403 NOT_PARTICIPANT`, `404`.

### 7.3 `WS /ws/{conversation_id}`  *(Phase 2)*
Real-time chat.

- **Auth:** token passed on connect (query param or subprotocol); must be a participant.
- **Flow:** on message, persist to `messages`, bump `conversation.updated_at`, and fan out via
  **Redis Pub/Sub** (multi-device). Emit in-app new-message notification.
- **Close codes:** `4401` unauthorized, `4403` not a participant, `4404` no conversation.

---

## 8. Reviews  (`/api/reviews`, plus reads on spaces/users)

Router file: create `backend/routers/reviews.py` and register it in `main.py`.

### Shared schema — `ReviewResponse`
```json
{
  "id": "uuid",
  "booking_id": "uuid",
  "reviewer_id": "uuid",
  "reviewee_id": "uuid",
  "space_id": 1,
  "rating": 5,
  "comment": "Great space, easy access.",
  "created_at": "2026-07-22T10:00:00Z"
}
```

### 8.1 `POST /reviews`
Submit a review after a booking completes.

- **Auth:** required
- **Request**
```json
{ "booking_id": "uuid", "space_id": 1, "reviewee_id": null, "rating": 5, "comment": "..." }
```
  (`space_id` set → reviewing a space; `reviewee_id` set → reviewing a user. Exactly one.)
- **Response `201`:** `ReviewResponse`.
- **Logic**
  - Booking must be `completed`; caller must be a participant in it.
  - `rating` 1–5 (check constraint).
  - Enforce unique `(booking_id, reviewer_id)` → `409 ALREADY_REVIEWED`.
  - Visibility: shown only after **both** parties submit **or** 14 days post-period.
  - Invalidate `rating:{space_id}` cache.
- **Errors:** `400 BOOKING_NOT_COMPLETED`, `403`, `409`.

### 8.2 `GET /spaces/{id}/reviews`
Reviews for a space.

- **Auth:** none
- **Response `200`:** `ReviewResponse[]` + `avg_rating`. Uses `idx_reviews_space`; avg cached
  at `rating:{space_id}` (TTL 1 hour).

### 8.3 `GET /users/{id}/reviews`
Reviews received by a user.

- **Auth:** none
- **Response `200`:** `ReviewResponse[]` (uses `idx_reviews_reviewee`).

---

## 9. Analytics  (`/api/analytics`)

Router file: create `backend/routers/analytics.py`. Admin/owner-facing; guard with an
admin/role check. Business metrics come from Postgres aggregation queries (visualized with
Recharts on the frontend).

### 9.1 `GET /analytics/bookings`
Booking counts over time.

- **Auth:** required (admin, or lister scoped to own spaces)
- **Query:** `from`, `to`, `interval` (`day`|`week`|`month`).
- **Response `200`**
```json
{ "series": [ { "period": "2026-06-01", "count": 12 } ] }
```

### 9.2 `GET /analytics/spaces/top`
Most viewed / most booked spaces.

- **Auth:** required (admin/owner)
- **Query:** `metric` (`views`|`bookings`), `limit`.
- **Response `200`:** ranked `[{ "space_id", "title", "value" }]`.

### 9.3 `GET /analytics/users/growth`
Signup growth curve.

- **Auth:** admin
- **Query:** `from`, `to`, `interval`.
- **Response `200`:** time series of new-user counts.

### 9.4 `GET /analytics/occupancy`
Occupancy rates by city / space type.

- **Auth:** admin
- **Query:** `group_by` (`city`|`type`), `from`, `to`.
- **Response `200`:** `[{ "group": "Springfield", "occupancy_rate": 0.62 }]`.

---

# Phase 2 — Payments  (`/api/payments`)

Implement after MVP is validated. Uses Stripe Payment Intents + Connect (marketplace payouts).

### P.1 `POST /payments/create-intent`
Initiate a Stripe payment for a confirmed booking.

- **Auth:** required (renter on the booking)
- **Request:** `{ "booking_id": "uuid" }`
- **Response `200`:** `{ "client_secret": "...", "payment_intent_id": "..." }`
- **Logic:** create a `payments` row (`pending`), create a Stripe PaymentIntent with the
  platform fee, return the client secret for Stripe Elements.

### P.2 `POST /payments/webhook`
Stripe async callback.

- **Auth:** Stripe signature verification (not a user token).
- **Handles:** `payment_intent.succeeded`, `payment_intent.payment_failed`, `payout.paid`.
- **Logic:** verify signature, sync `payments.status`, and on success advance the booking from
  `accepted` to `confirmed` (or `active` in the same write if `start_date` is already today).
  Must be idempotent (Stripe retries).
- **Response `200`** quickly to acknowledge.

---

## Suggested implementation checklist (per endpoint)
1. Define Pydantic request/response schemas in `schemas/`.
2. Write the CRUD/DB access in `crud/` (SQLAlchemy async session from `get_db`).
3. Wire Redis caching/locks in `caches/` where noted.
4. Implement the route in `routers/`, add auth dependency, register in `main.py`.
5. Add the standard error handler and map business errors to the codes above.
6. **Test in Swagger `/docs`** before building the frontend for it (per `notes.md`).
