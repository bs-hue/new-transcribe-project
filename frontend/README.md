# Frontend

React + TypeScript + Vite + Tailwind CSS + shadcn/ui. Entirely separate from the
backend — the only coupling is the API contract in
[`docs/API_SPECIFICATION.md`](../docs/API_SPECIFICATION.md).

## Layout

```
src/
├─ main.tsx              Entry point
├─ index.css             Design tokens (the ONLY place colours are defined)
├─ app/                  Shell, routing, providers
│  ├─ layouts/AppShell   Sidebar (module registry) + topbar
│  ├─ pages/             Phase 0 placeholder pages
│  ├─ providers.tsx      React Query provider
│  └─ router.tsx         Route table
├─ shared/
│  ├─ lib/api/           The only code that touches the network
│  │  ├─ client.ts       fetch wrapper; access token held in memory
│  │  ├─ errors.ts       Error envelope parsing + code -> friendly copy
│  │  ├─ hooks.ts        Typed React Query hooks
│  │  └─ types.ts        Types mirroring the API contract
│  ├─ lib/utils.ts       cn() class-name helper
│  └─ ui/                shadcn/ui primitives (owned by us, not a dependency)
├─ features/
│  ├─ auth/              Phase 3
│  └─ transcription/     Phase 3
├─ config/env.ts         Typed environment access
└─ test/setup.ts         Test setup
```

## Rules that keep this maintainable

- **No component calls `fetch`.** Data arrives via typed hooks from
  `shared/lib/api`. This is what makes components testable without a server.
- **No hardcoded colours.** Use semantic tokens (`bg-primary`,
  `text-muted-foreground`). A rebrand should touch `index.css` and nothing else.
- **Every async surface handles four states:** loading, empty, error (with a
  retry path), success.
- **`@/` means `src/`.** No `../../..` import chains.

## Commands

```powershell
npm run dev          # dev server on http://localhost:5173, /api proxied to :8000
npm run build        # type-check then production build
npm run typecheck    # tsc --noEmit
npm run lint         # eslint, including accessibility rules
npm test             # vitest
npm run format       # prettier
```

## Adding a shadcn/ui component

```powershell
npx shadcn@latest add dialog
```

`components.json` routes it to `src/shared/ui/`. The code is **copied into this
repo** — we own it and can edit it freely, and no upstream release can break our
UI.
