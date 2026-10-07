# Database Schema — campus_nest

## Enums


| Enum             | Values                                              |
| ---------------- | --------------------------------------------------- |
| `booking_status` | `pending`, `accepted`, `confirmed`, `active`, `cancelled`, `completed`, `declined` |
| `payment_status` | `pending`, `succeeded`, `failed`, `refunded`        |
| `payment_type`   | `single`,`recurring_per_month`,`recurring_per_week` |


```sql
CREATE TYPE booking_status AS ENUM ('pending', 'accepted', 'confirmed', 'active', 'cancelled', 'completed', 'declined');
CREATE TYPE payment_status AS ENUM ('pending', 'succeeded', 'failed', 'refunded');
CREATE TYPE payment_type   AS ENUM ('single', 'recurring_per_month', 'recurring_per_week');

-- Existing databases (enum values cannot be removed; add only):
-- ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'accepted' AFTER 'pending';
-- ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'active' AFTER 'confirmed';
-- ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'declined' AFTER 'completed';
```

---



## Tables



### `users`

Stores student accounts and profile information.


| Column        | Type        | Nullable | Default             | Notes                    |
| ------------- | ----------- | -------- | ------------------- | ------------------------ |
| `id`          | uuid        | NO       | `gen_random_uuid()` | Primary key              |
| `email`       | text        | NO       | —                   | Unique                   |
| `password`    | text        | NO       | —                   | bcrypt hash              |
| `username`    | text        | NO       | —                   |                          |
| `phone`       | text        | YES      | —                   |                          |
| `university`  | text        | YES      | —                   | For student verification |
| `description` | text        | YES      | —                   | Public bio, max 200 words |
| `is_verified` | boolean     | NO       | `false`             | Email/student verified   |
| `avatar_url`  | text        | YES      | —                   | SeaweedFS URL            |
| `created_at`  | timestamptz | NO       | `now()`             |                          |
| `updated_at`  | timestamptz | NO       | `now()`             |                          |


```sql
CREATE TABLE users (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email       text        NOT NULL UNIQUE,
    password    text        NOT NULL,
    username    text        NOT NULL,
    phone       text,
    university  text,
    description text,
    is_verified boolean     NOT NULL DEFAULT false,
    avatar_url  text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
```

> **Account deletion is a soft delete — never issue `DELETE FROM users`.** Two things make a hard delete unworkable. Once `bookings` and `payments` exist, their foreign keys deliberately do not cascade, so Postgres rejects the delete outright for any user with booking history. And for a user without that history the delete does succeed, but the `spaces.owner_id` cascade silently destroys their listings along with every `saved_spaces` and `view_history` row other users had pointing at them.
>
> "Delete my account" should instead anonymize the profile (blank `email`, `phone`, `username`, `description` and `avatar_url`) and set `is_active = false` on the user's spaces, which hides the listings while leaving bookings, payments and reviews intact and referentially valid. The `ON DELETE CASCADE` on `spaces.owner_id` stays as a safety net for genuine administrative hard deletes; it is not the normal path.
>
> To tell deactivated accounts apart from active ones, add a nullable `deleted_at timestamptz` and filter on `deleted_at IS NULL` at login and in any user lookup. Note the anonymized row still occupies the `email` unique index, so blank it to a unique placeholder rather than an empty string if the address should be reusable.

---



### `spaces`

Listings for storage spaces (closet, shelf, garage, basement, room) available to rent for storing belongings.


| Column           | Type          | Nullable | Default             | Notes                                                       |
| ---------------- | ------------- | -------- | ------------------- | ----------------------------------------------------------- |
| `id`             | integer       | NO       | identity            | Primary key, auto-increment                                 |
| `owner_id`       | uuid          | NO       | —                   | FK → `users.id` (cascade delete)                            |
| `title`          | text          | NO       | —                   | Listing headline                                            |
| `description`    | text          | YES      | —                   |                                                             |
| `address`        | text          | NO       | —                   | Street address (private; not shown until booking confirmed) |
| `city`           | text          | NO       | —                   | Indexed for search                                          |
| `postal_code`    | text          | YES      | —                   | ZIP/postal code                                             |
| `latitude`       | numeric(9,6)  | YES      | —                   | Exact geocoded lat (server-side only)                       |
| `longitude`      | numeric(9,6)  | YES      | —                   | Exact geocoded long (server-side only)                      |
| `price`          | numeric(10,2) | NO       | —                   |                                                             |
| `price_type`     | payment_type  | NO       | —                   |                                                             |
| `available_from` | date          | NO       | —                   |                                                             |
| `available_to`   | date          | NO       | —                   |                                                             |
| `is_active`      | boolean       | NO       | `true`              | Hide without deleting                                       |
| `view_count`     | integer       | NO       | `0`                 | Denormalized total views; increment on each listing view  |
| `created_at`     | timestamptz   | NO       | `now()`             |                                                             |
| `updated_at`     | timestamptz   | NO       | `now()`             |                                                             |
| `expired_at`     | timestamptz   | NO       |                     |                                                             |


```sql
CREATE TABLE spaces (
    id             integer       GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    owner_id       uuid          NOT NULL REFERENCES users(id) ON DELETE DELETE,
    title          text          NOT NULL,
    description    text,
    address        text          NOT NULL,
    city           text          NOT NULL,
    postal_code    text,
    latitude       numeric(9,6),
    longitude      numeric(9,6),
    price          numeric(10,2) NOT NULL,
    price_type     payment_type  NOT NULL,
    available_from date          NOT NULL,
    available_to   date          NOT NULL,
    is_active      boolean       NOT NULL DEFAULT true,
    view_count     integer       NOT NULL DEFAULT 0,
    created_at     timestamptz   NOT NULL DEFAULT now(),
    updated_at     timestamptz   NOT NULL DEFAULT now(),
    expired_at     timestamptz   NOT NULL
);

CREATE INDEX idx_spaces_owner   ON spaces (owner_id);
CREATE INDEX idx_spaces_city    ON spaces (city);
CREATE INDEX idx_spaces_dates   ON spaces (available_from, available_to);
CREATE INDEX idx_spaces_lat_lng ON spaces (latitude, longitude);
```

> **Geo notes:** `latitude`/`longitude` are populated by the Mapbox Geocoding API on create/update and are never returned to renters before a booking is confirmed. A fuzzed/approximate location (snapped to ~the block) is computed on the fly at request time from the exact coordinates — no stored approximate columns needed. For proximity/"near campus" search, filter on a bounding box over `latitude`/`longitude`, or enable **PostGIS** and add a `location geography(Point,4326)` generated column to use `ST_DWithin` for accurate radius queries.

---



### `space_images`

Photos attached to a space listing, stored in SeaweedFS.


| Column       | Type        | Nullable | Default             | Notes                             |
| ------------ | ----------- | -------- | ------------------- | --------------------------------- |
| `id`         | uuid        | NO       | `gen_random_uuid()` | Primary key                       |
| `space_id`   | integer     | NO       | —                   | FK → `spaces.id` (cascade delete) |
| `url`        | text        | NO       | —                   | SeaweedFS S3 URL of the original  |
| `sort_order` | integer     | NO       | `0`                 | Display order                     |
| `created_at` | timestamptz | NO       | `now()`             |                                   |


```sql
CREATE TABLE space_images (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id   integer     NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    url        text        NOT NULL,
    sort_order integer     NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_space_images_space ON space_images (space_id, sort_order);
```

> **Thumbnails:** not a column. On upload the backend also stores a 400px long-edge image beside the original. Its object name is the original filename plus `-thumb` before the extension (`3f2a9c1e-....jpg` and `3f2a9c1e-....-thumb.jpg`). List responses build `thumbnail_url` from `url` with that rule.

---



### `saved_spaces`

Watchlist rows created when a user favorites a space (the heart toggle on a listing).


| Column       | Type        | Nullable | Default | Notes                             |
| ------------ | ----------- | -------- | ------- | --------------------------------- |
| `user_id`    | uuid        | NO       | —       | FK → `users.id` (cascade delete)  |
| `space_id`   | integer     | NO       | —       | FK → `spaces.id` (cascade delete) |
| `created_at` | timestamptz | NO       | `now()` | Orders the "recently saved" list  |


**Primary key:** `(user_id, space_id)` — composite, so a space can only be saved once per user

```sql
CREATE TABLE saved_spaces (
    user_id    uuid        NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    space_id   integer     NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, space_id)
);

CREATE INDEX idx_saved_spaces_space ON saved_spaces (space_id);
```

> Whether the current viewer has saved a listing is computed per request with an `EXISTS` subquery; it is never stored on `spaces`. The listing-wide total is `COUNT(*)` on `saved_spaces` for that `space_id` (uses `idx_saved_spaces_space`). Toggling on should use `INSERT ... ON CONFLICT (user_id, space_id) DO NOTHING` so a double tap is idempotent.
>
> **API:** [`ApiDocumentation.md` §4 Saved Spaces (`/api/saved`)](ApiDocumentation.md#4-saved-spaces--apisaved).

---



### `view_history`

Per-user browsing history. One row per (user, space) pair; revisiting a listing refreshes `viewed_at` instead of inserting another row.


| Column      | Type        | Nullable | Default | Notes                             |
| ----------- | ----------- | -------- | ------- | --------------------------------- |
| `user_id`   | uuid        | NO       | —       | FK → `users.id` (cascade delete)  |
| `space_id`  | integer     | NO       | —       | FK → `spaces.id` (cascade delete) |
| `viewed_at` | timestamptz | NO       | `now()` | Last time this user viewed it     |


**Primary key:** `(user_id, space_id)` — composite, so a space can only appear once per user's history

```sql
CREATE TABLE view_history (
    user_id    uuid        NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    space_id   integer     NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    viewed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, space_id)
);

CREATE INDEX idx_view_history_user_time ON view_history (user_id, viewed_at);
CREATE INDEX idx_view_history_space     ON view_history (space_id);
```

> Recording a view should use `INSERT ... ON CONFLICT (user_id, space_id) DO UPDATE SET viewed_at = now()` so a re-view bumps the timestamp rather than failing or duplicating. Increment `spaces.view_count` on every view (including re-views); that counter is a total, not unique viewers, so it can exceed the number of `view_history` rows for the listing. `ON DELETE CASCADE` from `spaces` means a deleted listing disappears from history; there is no "this listing is no longer available" row left behind. Anonymous (logged-out) browsing is not stored here.
>
> **API:** [`ApiDocumentation.md` §5 View History (`/api/history`)](ApiDocumentation.md#5-view-history--apihistory).

---



### `bookings`

Records of a renter booking a space for a date range.


| Column         | Type           | Nullable | Default             | Notes                                       |
| -------------- | -------------- | -------- | ------------------- | ------------------------------------------- |
| `id`           | uuid           | NO       | `gen_random_uuid()` | Primary key                                 |
| `space_id`     | integer        | NO       | —                   | FK → `spaces.id`                            |
| `renter_id`    | uuid           | NO       | —                   | FK → `users.id`                             |
| `owner_id`     | uuid           | NO       | —                   | FK → `users.id`; listing owner copied at request time |
| `start_date`   | date           | NO       | —                   |                                             |
| `end_date`     | date           | NO       | —                   |                                             |
| `status`       | booking_status | NO       | `pending`           | Lifecycle: pending → accepted → confirmed → active → completed; terminals cancelled, declined |
| `price`        | numeric(10,2)  | NO       | —                   | Listing price copied at request time        |
| `price_type`   | payment_type   | NO       | —                   | Listing `price_type` copied at request time |
| `total_price`  | numeric(10,2)  | NO       | —                   | Computed at booking time                    |
| `special_deal` | numeric(10,2)  | NO       | `0`                 | Owner flat override; `0` means none         |
| `cancel_requested_by` | text    | YES      | `NULL`              | `'renter'` or `'owner'` when one party has requested cancel after confirmed/active; `NULL` if none |
| `created_at`   | timestamptz    | NO       | `now()`             |                                             |
| `updated_at`   | timestamptz    | NO       | `now()`             |                                             |


```sql
CREATE TABLE bookings (
    id           uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id     integer        NOT NULL REFERENCES spaces(id),
    renter_id    uuid           NOT NULL REFERENCES users(id),
    owner_id     uuid           NOT NULL REFERENCES users(id),
    start_date   date           NOT NULL,
    end_date     date           NOT NULL,
    status       booking_status NOT NULL DEFAULT 'pending',
    price        numeric(10,2)  NOT NULL,
    price_type   payment_type   NOT NULL,
    total_price  numeric(10,2)  NOT NULL,
    special_deal numeric(10,2)  NOT NULL DEFAULT 0,
    cancel_requested_by text    CHECK (cancel_requested_by IN ('renter', 'owner')),
    created_at   timestamptz    NOT NULL DEFAULT now(),
    updated_at   timestamptz    NOT NULL DEFAULT now()
);

CREATE INDEX idx_bookings_renter ON bookings (renter_id);
CREATE INDEX idx_bookings_owner  ON bookings (owner_id);
CREATE INDEX idx_bookings_space  ON bookings (space_id);
```

> Foreign keys deliberately omit `ON DELETE CASCADE`: a booking is a financial record, so deleting a user or space it references should be blocked rather than silently erasing history. `owner_id` is copied from `spaces.owner_id` at request time so lister queries (`view=owner`) do not join `spaces`. It does not update if the listing later changes hands. Note this conflicts with `spaces.owner_id` cascading from `users` — once this table exists, deleting a user who owns a booked space will fail on the booking constraint.

---



### `payments`

Stripe payment records tied to a booking.


| Column                     | Type           | Nullable | Default             | Notes                         |
| -------------------------- | -------------- | -------- | ------------------- | ----------------------------- |
| `id`                       | uuid           | NO       | `gen_random_uuid()` | Primary key                   |
| `booking_id`               | uuid           | NO       | —                   | FK → `bookings.id`            |
| `stripe_payment_intent_id` | text           | YES      | —                   | Unique; set after Stripe call |
| `amount`                   | numeric(10,2)  | NO       | —                   |                               |
| `currency`                 | text           | NO       | `'usd'`             | ISO 4217 code                 |
| `status`                   | payment_status | NO       | `pending`           | Synced from Stripe webhook    |
| `created_at`               | timestamptz    | NO       | `now()`             |                               |
| `updated_at`               | timestamptz    | NO       | `now()`             |                               |


```sql
CREATE TABLE payments (
    id                       uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id               uuid           NOT NULL REFERENCES bookings(id),
    stripe_payment_intent_id text           UNIQUE,
    amount                   numeric(10,2)  NOT NULL,
    currency                 text           NOT NULL DEFAULT 'usd',
    status                   payment_status NOT NULL DEFAULT 'pending',
    created_at               timestamptz    NOT NULL DEFAULT now(),
    updated_at               timestamptz    NOT NULL DEFAULT now()
);
```

---



### `conversations`

A messaging thread between a lister and a renter about a specific space. One per (space, renter) pair.


| Column       | Type        | Nullable | Default             | Notes                  |
| ------------ | ----------- | -------- | ------------------- | ---------------------- |
| `id`         | uuid        | NO       | `gen_random_uuid()` | Primary key            |
| `space_id`   | integer     | NO       | —                   | FK → `spaces.id`       |
| `lister_id`  | uuid        | NO       | —                   | FK → `users.id`        |
| `renter_id`  | uuid        | NO       | —                   | FK → `users.id`        |
| `created_at` | timestamptz | NO       | `now()`             |                        |
| `updated_at` | timestamptz | NO       | `now()`             | Updated on new message |


**Unique constraint:** `(space_id, renter_id)`

```sql
CREATE TABLE conversations (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id   integer     NOT NULL REFERENCES spaces(id),
    lister_id  uuid        NOT NULL REFERENCES users(id),
    renter_id  uuid        NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (space_id, renter_id)
);
```

---



### `messages`

Individual chat messages within a conversation.


| Column            | Type        | Nullable | Default             | Notes                                    |
| ----------------- | ----------- | -------- | ------------------- | ---------------------------------------- |
| `id`              | uuid        | NO       | `gen_random_uuid()` | Primary key                              |
| `conversation_id` | uuid        | NO       | —                   | FK → `conversations.id` (cascade delete) |
| `sender_id`       | uuid        | NO       | —                   | FK → `users.id`                          |
| `content`         | text        | NO       | —                   |                                          |
| `created_at`      | timestamptz | NO       | `now()`             |                                          |


```sql
CREATE TABLE messages (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id       uuid        NOT NULL REFERENCES users(id),
    content         text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_convo ON messages (conversation_id, created_at);
```

---



### `reviews`

Ratings submitted after a booking completes. Can review a space, a user, or both.


| Column        | Type        | Nullable | Default             | Notes                                      |
| ------------- | ----------- | -------- | ------------------- | ------------------------------------------ |
| `id`          | uuid        | NO       | `gen_random_uuid()` | Primary key                                |
| `booking_id`  | uuid        | NO       | —                   | FK → `bookings.id`                         |
| `reviewer_id` | uuid        | NO       | —                   | FK → `users.id`                            |
| `reviewee_id` | uuid        | YES      | —                   | FK → `users.id`; null if reviewing a space |
| `space_id`    | integer     | YES      | —                   | FK → `spaces.id`; null if reviewing a user |
| `rating`      | smallint    | NO       | —                   | 1–5 (check constraint)                     |
| `comment`     | text        | YES      | —                   |                                            |
| `created_at`  | timestamptz | NO       | `now()`             |                                            |


**Unique constraint:** `(booking_id, reviewer_id)` — one review per booking per reviewer

```sql
CREATE TABLE reviews (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id  uuid        NOT NULL REFERENCES bookings(id),
    reviewer_id uuid        NOT NULL REFERENCES users(id),
    reviewee_id uuid        REFERENCES users(id),
    space_id    integer     REFERENCES spaces(id),
    rating      smallint    NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (booking_id, reviewer_id)
);

CREATE INDEX idx_reviews_space    ON reviews (space_id);
CREATE INDEX idx_reviews_reviewee ON reviews (reviewee_id);
```

---



## Indexes


| Index                      | Table        | Columns                        | Purpose                                       |
| -------------------------- | ------------ | ------------------------------ | --------------------------------------------- |
| `idx_spaces_owner`         | spaces       | `owner_id`                     | Fetch listings by owner                       |
| `idx_spaces_city`          | spaces       | `city`                         | Search/filter listings                        |
| `idx_spaces_dates`         | spaces       | `available_from, available_to` | Date range queries                            |
| `idx_spaces_lat_lng`       | spaces       | `latitude, longitude`          | Bounding-box proximity search                 |
| `idx_spaces_location_gist` | spaces       | `location` (geography)         | PostGIS `ST_DWithin` radius search (optional) |
| `idx_space_images_space`   | space_images | `space_id, sort_order`         | Fetch a listing's photos in display order     |
| `saved_spaces_pkey`        | saved_spaces | `user_id, space_id`            | My saved list; uniqueness per user/space      |
| `idx_saved_spaces_space`   | saved_spaces | `space_id`                     | Save counts and reverse lookups               |
| `view_history_pkey`        | view_history | `user_id, space_id`            | Uniqueness per user/space; upsert target      |
| `idx_view_history_user_time` | view_history | `user_id, viewed_at`         | Recently viewed list, newest first            |
| `idx_view_history_space`   | view_history | `space_id`                     | Reverse lookups when a listing is deleted     |
| `idx_bookings_renter`      | bookings     | `renter_id`                    | My bookings (renter view)                     |
| `idx_bookings_owner`       | bookings     | `owner_id`                     | My bookings (owner view)                      |
| `idx_bookings_space`       | bookings     | `space_id`                     | Space availability checks                     |
| `idx_messages_convo`       | messages     | `conversation_id, created_at`  | Chat history pagination                       |
| `idx_reviews_space`        | reviews      | `space_id`                     | Space review listing                          |
| `idx_reviews_reviewee`     | reviews      | `reviewee_id`                  | User review listing                           |

