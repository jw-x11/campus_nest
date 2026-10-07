## Build Order

### 1. Auth
- Backend: Register, login, JWT, refresh, logout
- Frontend: Login/register pages, JWT storage, axios interceptor for token refresh, protected route wrapper

### 2. User Profile
- Backend: Get/update profile, avatar upload
- Frontend: Profile page, avatar upload UI

### 3. Spaces
- Backend: CRUD, image upload, Redis search cache
- Frontend: Listing creation form, search/filter page, space detail page, image gallery

### 4. Bookings
- Backend: Create with Redis lock, cancel, list mine
- Frontend: Booking form on space detail, "My Bookings" dashboard

### 5. Messages
- Backend: Conversation REST endpoints, WebSocket
- Frontend: Conversation list, chat UI with WebSocket connection

### 6. Reviews
- Backend: Submit, fetch by space/user
- Frontend: Review form (post-booking), star ratings on space detail and user profile

### 7. Analytics
- Backend: Endpoints for listing views, booking counts, occupancy rates, popular cities
- Frontend: Admin/owner dashboard with charts (bookings over time, top spaces, user signups)

---

> Finish the backend route and test it in Swagger (`/docs`) before building the frontend for it.

### Phase 2 — Payments (post-launch)
- Backend: Stripe payment intent, webhook
- Frontend: Stripe Elements checkout UI, payment confirmation page

---

## Stripe Services

**Payment Intents** — handles the actual charge when a renter books a space. Supports cards, Apple/Google Pay, and handles 3D Secure automatically.

**Connect** — since this is a marketplace (money flows from renter → platform → lister), Connect splits payments and pays out to listers. Without it you'd have to manually transfer money to listers.

**Webhooks** — listens for async events from Stripe (`payment_intent.succeeded`, `payment_intent.payment_failed`, `payout.paid`) to keep the `payments` table in sync. Required because the frontend can close before a payment confirms.

### Setup Flow
1. Create a regular Stripe account (for the platform)
2. Enable Stripe Connect in the dashboard
3. Listers onboard via Connect (Stripe collects their bank info)
4. When a renter pays, take a platform fee and Stripe routes the rest to the lister
