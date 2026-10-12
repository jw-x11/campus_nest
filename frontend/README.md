# Campus Nest — Frontend

React + Vite + React Router app. Styling is **Tailwind CSS v4** (via `@tailwindcss/vite`)
layered with the existing Campus Nest design tokens in `src/index.css`.

## Setup

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000 (proxies /api → http://127.0.0.1:5001)
npm run build    # production build to dist/
npm run preview  # preview the production build
```

## Tailwind CSS v4

- Plugin: `@tailwindcss/vite` registered in `vite.config.js` (`plugins: [react(), tailwindcss()]`).
- Entry: `src/index.css` starts with `@import "tailwindcss";` — this must stay the first line.
- No `tailwind.config.js` / `postcss.config.js` needed (v4 is CSS-first; define custom theme
  tokens with `@theme` in CSS if needed).
- The existing custom CSS (design tokens `--ink`, `--accent`, components `.wire-card`,
  `.btn`, `.field`, `.chip`, …) lives in the same file **after** the import, so both
  systems work together:
  - Use Tailwind utilities (`flex`, `grid`, `gap-4`, `p-4`, `md:...`) for layout/spacing in new JSX.
  - Keep `wire-card`, `btn btn-primary`, `field`, `pill`/`chip` for the neo-brutalist look.

Verify Tailwind is working: add a utility class (e.g. `className="flex gap-4"`) to any
component and confirm `npm run build` emits Tailwind utilities in `dist/assets/*.css`.

## Project structure

- `src/main.jsx` — entry, imports `index.css`, mounts `App` with router + context.
- `src/App.jsx` — routes (`/`, `/search`, `/map`, `/list`, `/space/:id`, `/book/:id`, …).
- `src/pages/` — page components.
- `src/components/` — shared UI (`Nav`, `ui`, `cards`, `Controls`, …).
- `src/context/AppContext.jsx` — global app state.
- `src/api.js`, `src/data.js` — API client / local data.
