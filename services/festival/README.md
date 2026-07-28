# festival service

**Owner (Wave):** B1  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Festival lifecycle, developer discount confirmation, schedules (up to 100% off).

## User stories

US-37, US-38, US-39

## Endpoints (to implement)

- `POST /api/v1/festival`
- `POST /api/v1/festival/{id}/entries/{gameId}/confirm`
- `POST /api/v1/festival/{id}/start`
- `POST /api/v1/festival/{id}/end`
- `GET  /api/v1/festival/active`

## Database

PostgreSQL `festival`

## Events

- **Out:** festival.started, festival.ended
- **In:** (none)

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/festival/health` and `/health` green

## Local run

Service starts via `docker compose up festival festival-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
