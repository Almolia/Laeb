# review service

**Owner (Wave):** B3  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Owner-only like/dislike + text reviews; emoji reactions; local ownership projection.

## User stories

US-19, US-20, US-21, US-22

## Endpoints (to implement)

- `POST /api/v1/review/games/{gameId}`
- `GET  /api/v1/review/games/{gameId}`
- `POST /api/v1/review/{reviewId}/reactions`

## Database

MongoDB `review`

## Events

- **Out:** (optional review.created)
- **In:** order.game_purchased, order.refund_issued

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/review/health` and `/health` green

## Local run

Service starts via `docker compose up review review-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
