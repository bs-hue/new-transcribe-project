# Feature: `auth`

**Status:** not implemented — Phase 3 (against the Phase 1 API).

Login and registration screens, session handling, and route guards.

## Planned contents

- `pages/LoginPage.tsx`, `pages/RegisterPage.tsx`
- `hooks/useAuth.ts` — current user, sign in, sign out
- `components/ProtectedRoute.tsx`, `components/RoleGuard.tsx`
- `api/` — typed hooks for `/auth/*`

## Decisions that constrain this feature

- The **access token lives in memory only** (`shared/lib/api/client.ts`), never in
  `localStorage` — anything in storage is readable by injected scripts.
- The **refresh token is an HttpOnly cookie**, so this code can neither read nor
  set it; refreshing means calling `POST /auth/refresh` and letting the browser
  send the cookie.
- `POST /auth/refresh` and `POST /auth/logout` require an `X-CSRF-Token` header
  matching the `csrf_token` cookie.
- A 401 with `TOKEN_EXPIRED` should trigger one refresh-and-retry, then fall back
  to sending the user to the login screen.

See `docs/API_SPECIFICATION.md` §2 and `docs/TECHNOLOGY_DECISIONS.md` §5.
