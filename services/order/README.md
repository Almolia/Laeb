# order service

**Owner (Wave):** B1  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Purchase, gift (+0.2% message surcharge), 12h refund, entitlements, purchase saga orchestration.

## User stories

US-15, US-16, US-17, US-18, US-36

## Endpoints (to implement)

- `POST /api/v1/order/purchase`
- `POST /api/v1/order/gift`
- `POST /api/v1/order/{id}/refund`
- `GET  /api/v1/order/library/me`

## Database

PostgreSQL `orders` (not `order`)

## Events

- **Out:** order.game_purchased, order.gift_sent, order.refund_issued
- **In:** (none for MVP; sync calls to catalog/wallet)

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/order/health` and `/health` green

## Local run

Service starts via `docker compose up order order-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
