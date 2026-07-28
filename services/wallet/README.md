# wallet service

**Owner (Wave):** A3  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Balances, append-only ledger, 70/30 split, top-up via mock-psp, gift-card redeem, refunds, trade settlement.

## User stories

US-14, US-34, US-35, US-36

## Endpoints (to implement)

- `GET  /api/v1/wallet/me`
- `POST /api/v1/wallet/top-up`
- `POST /api/v1/wallet/webhook/psp`
- `POST /api/v1/wallet/gift-cards/redeem`
- `POST /api/v1/wallet/debit`
- `POST /api/v1/wallet/credit`

## Database

PostgreSQL `wallet` (append-only ledger)

## Events

- **Out:** trade.payment_settled, wallet.topped_up
- **In:** trade.matched, order.refund_issued

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/wallet/health` and `/health` green

## Local run

Service starts via `docker compose up wallet wallet-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
