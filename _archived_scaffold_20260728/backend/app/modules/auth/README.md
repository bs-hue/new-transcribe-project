# Module: `auth`

**Status:** not implemented — Phase 1.

Owns identity: registration, login, token lifecycle, users, and roles. Effectively
part of the platform foundation: other modules depend on its *published contract*
(a current-user identity plus role checks, exposed through `core/dependencies.py`),
never on its internals.

## Planned layers

| Layer | Contents |
|---|---|
| `domain/` | `User`, `Role`, `RefreshToken` entities; password policy; repository ports |
| `application/` | `RegisterUser`, `Login`, `RefreshAccessToken`, `Logout`, `AssignRoles`, `ListUsers`, `DeleteOwnAccount` |
| `infrastructure/` | SQLAlchemy models and repositories; argon2 hashing; PyJWT token issuing |
| `interface/` | `/auth/*` and `/users/*` routers, request/response schemas, RBAC guards |

## Decisions already made

- Access token: JWT, 15-minute lifetime, held in browser memory only.
- Refresh token: opaque, **stored hashed**, rotated on every use; reuse of a
  rotated token revokes the whole chain.
- Transport: **HttpOnly + Secure + SameSite=Lax cookie**, with a double-submit
  `X-CSRF-Token` on `/auth/refresh` and `/auth/logout`.
- Passwords: **argon2id** via `argon2-cffi` (not `passlib` — unmaintained).
- Roles: `admin` and `user`, via a many-to-many `user_roles` table.

Rationale: `docs/TECHNOLOGY_DECISIONS.md` §5. Endpoints: `docs/API_SPECIFICATION.md` §2-3.
