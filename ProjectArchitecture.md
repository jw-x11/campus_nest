## 🏗️ Project Architecture Summary

### Project Outline

1. Problem
   - Students leave for summer but continue paying rent and need temporary storage.
   - Short-term renters struggle to find affordable, flexible housing near campus.
2. Solution
   - A verified, student-focused marketplace for summer subleases and storage rentals.
   - Support for housing-only, storage-only, or bundled listings.
3. Target Users
   - Students subleasing rooms or offering storage
   - Summer interns, visiting students, and local short-term renters
4. Value Proposition
   - Reduce wasted rent and storage costs
   - Safer and more efficient than informal channels
5. Next Steps
   - Validate demand on one campus
   - Build MVP and onboard early users

### App Features

- Post Space
  - Students list rooms, apartments, or unused space for storage
  - Set dates, price, and rules
- Find Space
  - Users search for short-term housing or storage
  - Filter by location, dates, price, and type
- Match & Communicate
  - In-app messaging between listers and renters
  - Verified student profiles
- Book & Pay
  - Secure payments for subleases or storage
  - Clear start and end dates
- Manage Rental
  - Move-in / move-out reminders
  - Reviews after rental ends

### Tech Stack

| Layer            | Technology                      |
| ---------------- | ------------------------------- |
| API Framework    | FastAPI + Uvicorn               |
| Database         | PostgresSQL                     |
| Media storage    | SeaweedFS (local S3)            |
| Cache / Sessions | Redis (aioredis)                |
| Auth             | JWT (python-jose) + bcrypt      |
| Payments         | Stripe API                      |
| Real-Time        | WebSockets + Redis Pub/Sub      |
| Testing          | pytest + httpx                  |
| Deployment       | Docker + Nginx + Railway/Render |

### Core API Endpoints

**Auth**

- `POST /auth/register` — create account
- `POST /auth/login` — returns JWT tokens
- `POST /auth/logout` — invalidate token in Redis
- `POST /auth/refresh` — issue new access token

**Spaces**

- `POST /spaces` — list a room/apartment/storage unit
- `GET /spaces` — search with filters (cached in Redis)
- `GET /spaces/{id}` — space detail (cached in Redis)
- `PUT /spaces/{id}` — update listing (invalidates cache)
- `DELETE /spaces/{id}` — remove listing
- `POST /spaces/{id}/images` — upload photos

**Bookings**

- `POST /bookings` — book a space (with Redis lock for availability)
- `GET /bookings/me` — my bookings
- `PATCH /bookings/{id}/cancel` — cancel booking

**Payments**

- `POST /payments/create-intent` — initiate Stripe payment
- `POST /payments/webhook` — Stripe callback

**Messages**

- `WS /ws/{conversation_id}` — real-time chat
- `GET /conversations` — list my conversations
- `GET /conversations/{id}/messages` — message history

**Reviews**

- `POST /reviews` — submit a review
- `GET /spaces/{id}/reviews` — space reviews
- `GET /users/{id}/reviews` — user reviews

---

## 📦 Key Libraries to Install

```bash
pip install fastapi uvicorn[standard] motor pymongo redis[asyncio] python-jose[cryptography] passlib[bcrypt] python-multipart stripe python-dotenv httpx pytest pytest-asyncio
```

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

