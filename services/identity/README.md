# identity service

**Owner (Wave):** A2  
**Status:** implemented

## Purpose

Registration, login (JWT), role-upgrade requests, admin grant/revoke (US-01…US-04).

## User stories

US-01, US-02, US-03, US-04

## Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/identity/auth/register` | public |
| POST | `/api/v1/identity/auth/login` | public |
| GET | `/api/v1/identity/auth/me` | any |
| POST | `/api/v1/identity/role-requests` | BASE_USER+ |
| GET | `/api/v1/identity/role-requests/me` | any |
| GET | `/api/v1/identity/role-requests` | ADMIN |
| POST | `/api/v1/identity/role-requests/{id}/approve` | ADMIN |
| POST | `/api/v1/identity/role-requests/{id}/reject` | ADMIN |
| POST | `/api/v1/identity/users/{userId}/roles` | ADMIN |
| DELETE | `/api/v1/identity/users/{userId}/roles/{role}` | ADMIN |
| GET | `/api/v1/identity/users/{userId}` | any |
| GET | `/api/v1/identity/users?ids=a,b` | any |

## Database

PostgreSQL `identity` — tables `users`, `user_roles`, `role_requests`, `outbox`.  
Partial unique index `uq_pending_request` on pending role requests.

## Events

- **Out:** `user.registered`, `user.role_granted` (via transactional outbox)
- **In:** none

## Env vars

`DATABASE_URL`, `JWT_SECRET`, `ADMIN_USERNAME` (default `admin`), `ADMIN_PASSWORD` (default `admin123`), `RABBITMQ_URL`, `EVENT_EXCHANGE`

## Decisions I made

- Role changes apply on the **next login** (new JWT). Documented trade-off for stateless JWT.
- Schema via `create_all` on startup + Alembic revision `0001_identity` for traceability.
- bcrypt pinned to 4.0.1 for passlib compatibility.

## Tests

```bash
docker compose exec identity pytest -q /app/tests
# or locally with PYTHONPATH=services/identity
pytest services/identity/tests -q
```

## Get a token

```bash
curl -s -X POST http://localhost:8000/api/v1/identity/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

## Known gaps

- No OAuth providers (email/password only).
- Profile display name / avatar is Profile service (B3), not here.
