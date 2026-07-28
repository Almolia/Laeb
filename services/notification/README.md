# notification service

**Owner (Wave):** Wave B (shared)  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Pure event consumer: email / in-app notifications for gifts, reviews, trades, refunds.

## User stories

cross-cutting (supports US-16, US-10, US-28, US-18, ...)

## Endpoints (to implement)

- `GET /api/v1/notification/me`

## Database

MongoDB `notification` (log)

## Events

- **Out:** (none)
- **In:** user.role_granted, game.published, order.game_purchased, order.gift_sent, order.refund_issued, trade.settled, item.granted, festival.started, wallet.topped_up

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/notification/health` and `/health` green

## Local run

Service starts via `docker compose up notification notification-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
