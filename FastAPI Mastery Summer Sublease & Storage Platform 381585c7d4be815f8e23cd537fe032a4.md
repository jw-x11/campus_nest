# FastAPI Mastery Plan

## Overview

This is your personalized 1-month roadmap to learn **FastAPI** and build a **Summer Sublease & Storage Platform** — a full-stack, production-ready app with **MongoDB (NoSQL)** and **Redis** integration. Since you already know Python, you'll move fast.

---

## 🗓️ Week 1: FastAPI Fundamentals (Days 1–7)

### Day 1 — FastAPI Basics

- Install FastAPI and Uvicorn: `pip install fastapi uvicorn`
- Understand ASGI vs WSGI
- Create your first `main.py` with a Hello World endpoint
- Learn `@app.get`, `@app.post`, `@app.put`, `@app.delete`
- Run dev server: `uvicorn main:app --reload`
- Explore the auto-generated Swagger docs at `/docs`

**Resources:** FastAPI official docs — [https://fastapi.tiangolo.com/tutorial/](https://fastapi.tiangolo.com/tutorial/)

### Day 2 — Path & Query Parameters, Request Bodies

- Path parameters: `/spaces/{space_id}`
- Query parameters: `/spaces?city=NYC&max_price=1000`
- Request bodies using Pydantic `BaseModel`
- Optional vs required fields
- Practice: Build a mock `/spaces` CRUD endpoint (in-memory list)

### Day 3 — Pydantic Deep Dive

- Validators (`@validator`, `field_validator`)
- Nested models (e.g. `Address` inside `SpaceListing`)
- `model_config` for aliases and extra field handling
- Response models and `response_model=` parameter
- Practice: Define models for `SpaceListing`, `User`, `Booking`

### Day 4 — Dependency Injection

- `Depends()` function
- Reusable dependencies (pagination, auth headers)
- Nested dependencies
- Practice: Create a `get_current_user` dependency stub

### Day 5 — Routers & App Structure

- `APIRouter` for splitting routes into modules
- Recommended project structure:

```
app/
├── main.py
├── routers/
│   ├── spaces.py
│   ├── users.py
│   ├── bookings.py
│   └── auth.py
├── models/
├── schemas/
├── db/
└── core/
```

- `include_router()` with prefixes and tags
- Practice: Scaffold the project folder for the sublease platform

### Day 6 — Error Handling & Middleware

- `HTTPException` with custom detail and status codes
- Custom exception handlers
- `@app.middleware("http")` for logging
- CORS middleware setup (`CORSMiddleware`)
- Practice: Add proper error responses to your space/user routes

### Day 7 — Review & Mini Project

- Build a complete in-memory CRUD API for `SpaceListing`
- Test all endpoints via Swagger UI
- Write basic pytest tests using `TestClient`
- **Checkpoint:** You can build, structure, and test a FastAPI app ✅

---

## 🗓️ Week 2: MongoDB + NoSQL Integration (Days 8–14)

### Day 8 — MongoDB Fundamentals

- Install MongoDB locally or use MongoDB Atlas (free tier)
- Install Motor (async MongoDB driver): `pip install motor`
- Understand documents, collections, and the NoSQL mindset vs SQL
- Key differences: no joins, flexible schema, embedded documents
- Practice: Connect to MongoDB, insert and query a test document

### Day 9 — Motor (Async MongoDB) with FastAPI

- Create a `db/mongodb.py` connection module
- Use `motor.motor_asyncio.AsyncIOMotorClient`
- Lifespan events: connect on startup, close on shutdown
- Practice: Wire up the `spaces` collection and test basic CRUD

### Day 10 — Data Modeling for the Platform

Design your MongoDB collections:

- **users** — `{ _id, email, hashed_password, is_verified, university, created_at }`
- **spaces** — `{ _id, owner_id, type (room/apartment/storage), title, description, address (embedded), price, dates, rules, images, status }`
- **bookings** — `{ _id, space_id, renter_id, start_date, end_date, total_price, payment_status, created_at }`
- **messages** — `{ _id, conversation_id, sender_id, receiver_id, content, read, created_at }`
- **reviews** — `{ _id, booking_id, reviewer_id, reviewee_id, rating, comment, created_at }`

### Day 11 — Indexes & Querying

- Create indexes for performance: `email` (unique), `space.address.city`, `booking.renter_id`
- Geospatial index for location search (`2dsphere`)
- Filter, sort, skip, limit for pagination
- Practice: Build `/spaces` search endpoint with city, price, date filters

### Day 12 — Relationships in NoSQL

- Embedding vs referencing (when to use each)
- Embed: `address` inside `space`, `images` array inside `space`
- Reference: `owner_id` in `space` points to `users` collection
- Lookup pattern: fetch space then fetch owner separately (no joins)
- Practice: Implement `GET /spaces/{id}` that includes owner profile

### Day 13 — File Uploads & Images

- `UploadFile` and `File` in FastAPI
- Save images to local disk or integrate with S3/Cloudinary
- Store image URLs inside the `space` document
- Practice: Add `POST /spaces/{id}/images` endpoint

### Day 14 — Review & Test

- Complete CRUD for `spaces` and `users` backed by MongoDB
- Write pytest tests with a test MongoDB database
- **Checkpoint:** NoSQL-backed REST API for core entities is working ✅

---

## 🗓️ Week 3: Redis, Auth & Advanced Features (Days 15–21)

### Day 15 — Redis Fundamentals

- Install Redis locally or use Redis Cloud (free tier)
- Install client: `pip install redis[asyncio]` or `pip install aioredis`
- Core data structures: strings, hashes, lists, sets, sorted sets
- TTL (Time To Live) — critical for caching and session management
- Practice: Connect to Redis, set/get keys, test TTL expiry

### Day 16 — Redis Use Case 1: Session & Token Storage

- JWT authentication flow: access token + refresh token
- Install: `pip install python-jose[cryptography] passlib[bcrypt]`
- Store refresh tokens in Redis with TTL = expiry time
- Blacklist invalidated tokens on logout
- Practice: Implement `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`

### Day 17 — Redis Use Case 2: Caching

- Cache expensive queries (e.g. space search results, space details)
- Cache-aside pattern: check Redis first → hit returns cached → miss queries MongoDB and stores in Redis
- Cache invalidation: delete cache when space is updated/deleted
- Practice: Add Redis caching to `GET /spaces` and `GET /spaces/{id}`

### Day 18 — Redis Use Case 3: Rate Limiting

- Protect endpoints (login, register, messaging) from abuse
- Sliding window counter in Redis: `INCR key`, `EXPIRE key`
- Implement as a FastAPI dependency: `Depends(rate_limit(max=10, window=60))`
- Practice: Rate limit `POST /auth/login` to 10 attempts per minute per IP

### Day 19 — Authentication & Authorization

- OAuth2 with Password flow
- `get_current_user` dependency using JWT decode
- Role-based access: `lister` vs `renter` vs `admin`
- Protect routes: only space owners can edit their listings
- Practice: Secure all mutating endpoints

### Day 20 — Real-Time Messaging

- WebSockets in FastAPI: `@app.websocket("/ws/{conversation_id}")`
- Redis Pub/Sub for broadcasting messages between connections
- Store messages in MongoDB for persistence
- Practice: Build a basic in-app chat between lister and renter

### Day 21 — Review & Integration

- Ensure auth is wired into all protected routes
- Test Redis caching and confirm cache hits
- Test WebSocket chat manually
- **Checkpoint:** Auth, Redis caching, rate limiting, and messaging all working ✅

---

## 🗓️ Week 4: Bookings, Reviews & Production (Days 22–30)

### Day 22 — Booking Flow

- `POST /bookings` — create booking (check date availability first)
- Availability check: query MongoDB for overlapping bookings
- Use Redis to lock dates temporarily during checkout (prevent double-booking)
- `GET /bookings/me` — renter's booking history
- `GET /spaces/{id}/bookings` — lister's dashboard

### Day 23 — Payment Integration

- Integrate Stripe (or mock it): `pip install stripe`
- `POST /payments/create-intent` — create Stripe PaymentIntent
- Webhook: `POST /payments/webhook` — handle Stripe events (payment success/fail)
- Update booking `payment_status` on confirmed payment
- Practice: Test with Stripe test keys and CLI

### Day 24 — Reviews System

- Only allow reviews after a booking is completed
- `POST /reviews` — submit review for space or user
- `GET /spaces/{id}/reviews` — list reviews with average rating
- Update space's cached rating in Redis when new review is added

### Day 25 — Search & Filtering

- Advanced space search: location (geo), date range, price range, type
- MongoDB `$geoNear` for proximity search
- Text search with `$text` on title/description
- Cache search results in Redis with a composite cache key

### Day 26 — Background Tasks & Email

- FastAPI `BackgroundTasks` for non-blocking operations
- Send booking confirmation emails in background
- Use `python-multipart`, `emails`, or integrate SendGrid
- Move-in / move-out reminder logic (scheduled or event-driven)

### Day 27 — Testing

- `pytest` + `httpx` for async test client
- Use a separate test MongoDB database and flush Redis between tests
- Test coverage for: auth flow, space CRUD, booking creation, reviews
- Fixtures for database seeding

### Day 28 — Dockerize the App

- Write `Dockerfile` for FastAPI app
- `docker-compose.yml` with services: `app`, `mongodb`, `redis`
- Environment variables via `.env` and `python-dotenv`
- Practice: `docker compose up` should boot the entire stack

### Day 29 — Deployment

- Deploy options: **Railway**, **Render**, or [**fly.io**](http://fly.io) (all have free tiers)
- Use MongoDB Atlas and Redis Cloud for managed cloud databases
- Set environment variables in deployment dashboard
- Configure CORS for your frontend domain

### Day 30 — Final Polish & Documentation

- Review all endpoints in Swagger (`/docs`)
- Add `description`, `summary`, and `tags` to all routes
- Write a `README.md` with setup instructions
- **Final Checkpoint:** Full platform is deployed and documented ✅



## ✅ Daily Habit Tips

- Spend **30 min reading docs**, **90 min coding**, **3s0 min reviewing**
- Commit code daily to GitHub — track your progress
- Test every endpoint in Swagger before moving on
- When stuck, check FastAPI GitHub issues and the Discord community
- By Day 15, you'll have a working backend — the second half is refinement