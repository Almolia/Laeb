# identity service

**Owner (Wave):** A2  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Registration, login (JWT), roles, role-upgrade requests, admin grant/revoke.

## User stories

US-01, US-02, US-03, US-04

## Endpoints (to implement)

- `POST /api/v1/identity/register`
- `POST /api/v1/identity/login`
- `POST /api/v1/identity/logout`
- `POST /api/v1/identity/role-requests`
- `POST /api/v1/identity/roles/grant`
- `POST /api/v1/identity/roles/revoke`
- `GET  /api/v1/identity/me`

## Database

PostgreSQL database `identity` (user `identity_user`)

## Events

- **Out:** user.registered, user.role_granted
- **In:** (none required for MVP)

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/identity/health` and `/health` green

## Local run

Service starts via `docker compose up identity identity-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
