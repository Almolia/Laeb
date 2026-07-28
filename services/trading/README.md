# trading service

**Owner (Wave):** B2  
**Status:** stub (healthy) — implement domain logic here

## Purpose

In-game items, grants, buy/sell order book, 5-minute batch matching engine, settlement saga.

## User stories

US-23, US-24, US-25, US-26, US-27, US-28

## Endpoints (to implement)

- `POST /api/v1/trading/items`
- `POST /api/v1/trading/items/{id}/grant`
- `POST /api/v1/trading/orders/buy`
- `POST /api/v1/trading/orders/sell`
- `GET  /api/v1/trading/orders`
- `GET  /api/v1/trading/inventory/me`

## Database

PostgreSQL `trading` + Redis order-book cache

## Events

- **Out:** trade.matched, trade.settled, item.granted
- **In:** trade.payment_settled

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/trading/health` and `/health` green

## Local run

Service starts via `docker compose up trading trading-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
