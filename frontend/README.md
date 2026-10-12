# Campus Nest — Frontend

React + Vite + React Router app. Styling is **Tailwind CSS v4** (via `@tailwindcss/vite`)
on top of the Campus Nest palette (ink `#2b2b2b`, canvas `#e7e5df`, accent `#ffd22e`).
Theme: minimal, clean — white cards, 1px borders, subtle shadows.

## Setup

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000 (proxies /api → http://127.0.0.1:5001)
npm run build    # production build to dist/
npm run preview  # preview the production build
```

## Tailwind CSS v4

- Plugin: `@tailwindcss/vite` registered in `vite.config.js`.
- Entry: `src/index.css` starts with `@import "tailwindcss";`, declares the palette in
  `@theme` (`bg-ink`, `bg-canvas`, `bg-accent`, …), then a small set of shared
  classes (`.card`, `.btn`, `.input`, `.badge`, `.nav`, …).
- No `tailwind.config.js` needed (v4 is CSS-first).

## API client

`src/api.js` targets the **real backend** (`backend/routers/*`, envelope
`{ code, message, data }`), not the aspirational `docs/ProjectArchitecture.md` endpoint
list (that doc is out of sync with the code):

- Auth: `POST /auth/register|login|logout`, users: `GET|PUT /users/me`, `POST /users/me/avatar`
- Spaces: `GET /spaces/all` (aliases `kw pc from to price-type min max pg pg-size sort order`),
  `GET /spaces/me`, `GET /spaces/from/{owner}`, `POST /spaces/post`, `GET|PUT|DELETE /spaces/{id}`,
  `PATCH /spaces/{id}/accepting`, `PUT /spaces/renew/{id}`, `POST /spaces/{id}/images`
- Saved: `GET /saved/list`, `POST|DELETE|GET /saved/{id}`
- History: `GET /history/list` (cursor pagination), `POST|DELETE /history/{id}`, `DELETE /history/clear`
- Bookings: `POST /bookings/`, `GET /bookings/me` (`view=renter|owner`, `status=…`),
  `GET|PUT /bookings/details/{id}`, `PATCH /bookings/cancel|/cancel/withdraw|/accept|/confirm|/decline|/special`

There is **no** messaging, review, or analytics API in the backend yet (`main.py` TODOs),
so Messages is an honest local-only pilot preview.

## Routes

- `/` landing · `/search` browse+filters · `/map` map view
- `/space/:id` detail · `/book/:id` request to book · `/bookings` my bookings (renter/host tabs, full lifecycle: cancel, withdraw, accept, decline, confirm, special deal, change dates)
- `/list` list a space · `/profile` account, edit profile, avatar, listing management (pause/resume, renew, delete)
- `/saved` watchlist · `/history` recently viewed · `/messages` pilot preview · `/login`

## Project structure

- `src/main.jsx` — entry, imports `index.css`, mounts `App` with router + context.
- `src/App.jsx` — routes + `RequireAuth` guard + global `Nav`/`Footer`.
- `src/pages/` — one file per route (see above).
- `src/components/` — `Nav`, `Footer`, `ui` (Field, StatusBadge, Empty/Loading/Error states, Avatar), `cards` (SpaceCard, SpaceRow, SaveButton), `icons`.
- `src/context/AppContext.jsx` — session user + saved set.
- `src/api.js`, `src/data.js` — API client / static metadata.
