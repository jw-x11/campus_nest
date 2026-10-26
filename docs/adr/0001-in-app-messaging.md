# ADR-001: In-app messaging for CampusNest

**Status:** Accepted (backend implemented)
**Deciders:** Project owner

## Context

What the repo already has:
- FastAPI, async SQLAlchemy and Postgres, with Alembic migrations.
- Redis with a helper layer in `config/cache_config.py`.
- Bearer-token auth with a session cache.
- A `bookings` table with `renter_id` and `owner_id`.
- `docs/notes.md` already plans "Conversation REST endpoints, WebSocket". `main.py` has a `TODO: SocketIO live message`.

The natural use case is a renter and a space owner talking about a listing or a booking. Messaging also needs to survive reconnects, show unread counts, and work if the user has several tabs open.

## Decision

Postgres is the source of truth. Messages are sent and read over REST, and a native FastAPI WebSocket pushes new messages live. Redis pub/sub fans messages out to WebSocket connections. If the socket is down, the client falls back to REST.

## Options Considered

| | A. REST polling only | B. REST + native WebSocket + Redis pub/sub (recommended) | C. Socket.IO | D. Third-party (Stream, Sendbird) |
|---|---|---|---|---|
| Complexity | Low | Medium | Medium-high | Low to integrate |
| Real-time | Poor (delay of seconds) | Good | Good | Good |
| Fit with the stack | Perfect | Native to FastAPI, reuses Redis | Needs an extra ASGI wrapper | Replaces auth and DB |
| Cost | Free | Free | Free | Per-MAU fees |
| Scales past one process | Yes | Yes, via Redis | Yes, via Redis | Yes |

Option A is a good first milestone but not the final design. Option C only pays off for rooms and automatic reconnect; plain WebSocket is enough for 1:1 chat. Option D hands user data to a vendor and doesn't suit a student project.

## Data model

```
conversations
  id uuid pk
  space_id int fk spaces        -- what the chat is about
  booking_id uuid fk bookings null
  renter_id uuid fk users
  owner_id  uuid fk users
  last_message_at timestamptz   -- sorts the inbox
  created_at
  UNIQUE (space_id, renter_id, owner_id)   -- one thread per pair per listing

messages
  id uuid pk
  conversation_id fk
  sender_id fk users
  body text
  client_msg_id uuid            -- idempotency key for retries
  created_at timestamptz
  INDEX (conversation_id, created_at DESC)
  UNIQUE (conversation_id, sender_id, client_msg_id)

conversation_reads                -- or two columns on conversations
  conversation_id, user_id, last_read_at
```

- **Two participants only.** Use the owner/renter columns, as `bookings` does, instead of a generic participants table. Add one later for group chats.
- **Unread count** is the number of messages in the conversation with `created_at > last_read_at` and `sender_id != me`. Cache it per user in Redis if it gets hot.
- **Pagination** is keyset-based on `(created_at, id)`, not offset.

## API

REST (under `/api/messages`, behind the existing `default_limit`):
- `POST /conversations` finds or creates the thread for a space (the "Message owner" button).
- `GET /conversations` is the inbox, with last message and unread count.
- `GET /conversations/{id}/messages?before=...` returns a page of history.
- `POST /conversations/{id}/messages` sends a message and works without a socket.
- `POST /conversations/{id}/read` marks the thread as read.

WebSocket: `GET /ws`, one connection per client tab, not one per conversation.
- The server sends `{type:"message", conversation_id, message}`, plus read receipts and unread-count updates.
- The client sends `{type:"send", ...}` and `{type:"typing", ...}`. Only `send` is persisted.

## Flow

1. The sender posts or sends a message. The server checks they are a participant and inserts the row. The `client_msg_id` unique key makes retries safe.
2. After the commit, the server publishes to the Redis channel `user:{recipient_id}`, and to the sender's channel so their other tabs update.
3. Each app process keeps a map of `user_id -> sockets` and subscribes to the channels of its connected users. It forwards messages to those sockets.
4. On reconnect, the client calls `GET messages?after=<last seen>` to fill any gap. Redis pub/sub is fire-and-forget, so the database guarantees nothing is lost.

## Codebase-specific notes

- **WebSocket auth.** `get_current_user` reads the `Authorization` header, which browsers can't set on a WebSocket. Use a short-lived one-time ticket from `POST /ws/ticket`, or a token in the first message after connect. Don't put the long-lived bearer token in the URL (it ends up in logs). Reuse `get_raw_user_by_token` once the token is in hand.
- **Lifespan.** Start the Redis subscriber task in the `lifespan` in `main.py`, next to the existing jobs, and cancel it on shutdown.
- **Rate limiting.** Add a stricter limit on send via `rate_limit("...")`, and cap message length (e.g. 2,000 characters).
- **Authorization.** Every read and write must check the caller is the renter or owner of the conversation. Block sending if either user is deleted.
- **CORS and nginx.** `allow_origins=["*"]` is fine for dev. nginx needs the `Upgrade` and `Connection` headers and a long read timeout for `/ws`.
- **Cache helpers.** `cache_config` has no pub/sub wrapper; add a small `caches/messages.py` for publish/subscribe and unread counters.
- **Migrations.** Add the new models and an Alembic revision in `migrations/versions`.

## Trade-off Analysis

The REST-plus-socket split keeps the mental model simple (database is the truth, socket is a speed-up) and gives a clean fallback. The cost is extra moving parts: socket auth, a subscriber task per process, and harder tests.

## Consequences

- **Easier:** multi-tab support, offline catch-up, a working non-live feature before any socket code exists.
- **Harder:** WebSocket auth, running one subscriber task per process, testing socket flows.
- **Revisit later:** attachments (S3 upload exists in `utils/s3.py`), push/email notifications for offline users (a `jobs/`-style task), moderation and blocking, message retention, Redis Streams if replay guarantees are needed.

## Implementation notes

What the backend build settled that the design above left open:

- **Read state** is two columns on `conversations` (`renter_last_read_at`, `owner_last_read_at`), not a separate table.
- **`send_message` lives in `crud/messages.py`**, following the existing pattern where CRUD commits to the database and then updates the cache (as `crud/users.py` does). REST and the WebSocket both call it. It increments the unread count and publishes only for a new message, after the commit.
- **Unread cache** `msg:unread:{user_id}` is a hash. An increment only applies when the hash already exists (a Lua check), so an expired key is never recreated partly filled. A miss recounts from Postgres.
- **WebSocket auth**: `POST /api/messages/ws-ticket` trades the bearer token for a 30-second single-use ticket. The socket connects to `/api/messages/ws?ticket=...`. Every 30 seconds the hub's heartbeat checks that the session token behind each socket is still valid and closes the socket with code 4401 if not, which covers logout and logout-all.
- **Hub** (`utils/message_hub.py`) has its own Redis client with no read timeout, for the pub/sub connection.
- **Rate limit**: a `message` tier (30/minute, 500/hour) applies to REST and WebSocket sends.

## Action Items

1. [ ] Models, Alembic migration and schemas for `conversations`, `messages` and reads.
2. [ ] `crud/messages.py` and REST router, tested in Swagger.
3. [ ] Unread counts and mark-as-read.
4. [ ] Redis publish on send, WebSocket ticket auth and the `/ws` endpoint with a connection manager.
5. [ ] Subscriber task in `lifespan`, nginx upgrade config, rate limits.
6. [ ] Frontend inbox, chat view, and reconnect with catch-up.
7. [ ] Tests: participant authorization, idempotent send, pagination, two-client delivery.

Build steps 1 to 3 first: that gives a working, non-live messaging feature the frontend can use right away, and the WebSocket becomes an add-on.
