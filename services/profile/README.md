# profile service

**Owner (Wave):** B3  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Display name, avatar, purchased-games projection, top-5 posts widget, online presence (Redis TTL).

## User stories

US-05, US-06, US-07, US-08

## Endpoints (to implement)

- `GET  /api/v1/profile/{userId}`
- `PUT  /api/v1/profile/me`
- `POST /api/v1/profile/me/heartbeat`

## Database

PostgreSQL `profile` + Redis presence keys

## Events

- **Out:** (optional profile.updated)
- **In:** user.registered, order.game_purchased, order.refund_issued, forum.post_stats_changed

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/profile/health` and `/health` green

## Local run

Service starts via `docker compose up profile profile-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
