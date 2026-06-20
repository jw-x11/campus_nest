# Database Schema — campus_nest

## Enums

| Enum | Values |
|---|---|
| `space_type` | `room`, `apartment`, `storage` |
| `booking_status` | `pending`, `confirmed`, `cancelled`, `completed` |
| `payment_status` | `pending`, `succeeded`, `failed`, `refunded` |

---

## Tables

### `users`
Stores student accounts and profile information.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `email` | text | NO | — | Unique |
| `password_hash` | text | NO | — | bcrypt hash |
| `full_name` | text | NO | — | |
| `phone` | text | YES | — | |
| `university` | text | YES | — | For student verification |
| `is_verified` | boolean | NO | `false` | Email/student verified |
| `avatar_url` | text | YES | — | SeaweedFS URL |
| `created_at` | timestamptz | NO | `now()` | |
| `updated_at` | timestamptz | NO | `now()` | |

---

### `spaces`
Listings for rooms, apartments, or storage units available for sublease.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `owner_id` | uuid | NO | — | FK → `users.id` |
| `type` | space_type | NO | — | `room`, `apartment`, or `storage` |
| `title` | text | NO | — | Listing headline |
| `description` | text | YES | — | |
| `address` | text | NO | — | |
| `city` | text | NO | — | Indexed for search |
| `price_per_month` | numeric(10,2) | NO | — | |
| `available_from` | date | NO | — | |
| `available_to` | date | NO | — | |
| `is_active` | boolean | NO | `true` | Hide without deleting |
| `rules` | text | YES | — | House rules |
| `created_at` | timestamptz | NO | `now()` | |
| `updated_at` | timestamptz | NO | `now()` | |

---

### `space_images`
Photos attached to a space listing, stored in SeaweedFS.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `space_id` | uuid | NO | — | FK → `spaces.id` (cascade delete) |
| `url` | text | NO | — | SeaweedFS S3 URL |
| `sort_order` | integer | NO | `0` | Display order |
| `created_at` | timestamptz | NO | `now()` | |

---

### `bookings`
Records of a renter booking a space for a date range.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `space_id` | uuid | NO | — | FK → `spaces.id` |
| `renter_id` | uuid | NO | — | FK → `users.id` |
| `start_date` | date | NO | — | |
| `end_date` | date | NO | — | |
| `status` | booking_status | NO | `pending` | Lifecycle state |
| `total_price` | numeric(10,2) | NO | — | Computed at booking time |
| `created_at` | timestamptz | NO | `now()` | |
| `updated_at` | timestamptz | NO | `now()` | |

---

### `payments`
Stripe payment records tied to a booking.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `booking_id` | uuid | NO | — | FK → `bookings.id` |
| `stripe_payment_intent_id` | text | YES | — | Unique; set after Stripe call |
| `amount` | numeric(10,2) | NO | — | |
| `currency` | text | NO | `'usd'` | ISO 4217 code |
| `status` | payment_status | NO | `pending` | Synced from Stripe webhook |
| `created_at` | timestamptz | NO | `now()` | |
| `updated_at` | timestamptz | NO | `now()` | |

---

### `conversations`
A messaging thread between a lister and a renter about a specific space. One per (space, renter) pair.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `space_id` | uuid | NO | — | FK → `spaces.id` |
| `lister_id` | uuid | NO | — | FK → `users.id` |
| `renter_id` | uuid | NO | — | FK → `users.id` |
| `created_at` | timestamptz | NO | `now()` | |
| `updated_at` | timestamptz | NO | `now()` | Updated on new message |

**Unique constraint:** `(space_id, renter_id)`

---

### `messages`
Individual chat messages within a conversation.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `conversation_id` | uuid | NO | — | FK → `conversations.id` (cascade delete) |
| `sender_id` | uuid | NO | — | FK → `users.id` |
| `content` | text | NO | — | |
| `created_at` | timestamptz | NO | `now()` | |

---

### `reviews`
Ratings submitted after a booking completes. Can review a space, a user, or both.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | uuid | NO | `gen_random_uuid()` | Primary key |
| `booking_id` | uuid | NO | — | FK → `bookings.id` |
| `reviewer_id` | uuid | NO | — | FK → `users.id` |
| `reviewee_id` | uuid | YES | — | FK → `users.id`; null if reviewing a space |
| `space_id` | uuid | YES | — | FK → `spaces.id`; null if reviewing a user |
| `rating` | smallint | NO | — | 1–5 (check constraint) |
| `comment` | text | YES | — | |
| `created_at` | timestamptz | NO | `now()` | |

**Unique constraint:** `(booking_id, reviewer_id)` — one review per booking per reviewer

---

## Indexes

| Index | Table | Columns | Purpose |
|---|---|---|---|
| `idx_spaces_owner` | spaces | `owner_id` | Fetch listings by owner |
| `idx_spaces_city_type` | spaces | `city, type` | Search/filter listings |
| `idx_spaces_dates` | spaces | `available_from, available_to` | Date range queries |
| `idx_bookings_renter` | bookings | `renter_id` | My bookings |
| `idx_bookings_space` | bookings | `space_id` | Space availability checks |
| `idx_messages_convo` | messages | `conversation_id, created_at` | Chat history pagination |
| `idx_reviews_space` | reviews | `space_id` | Space review listing |
| `idx_reviews_reviewee` | reviews | `reviewee_id` | User review listing |
