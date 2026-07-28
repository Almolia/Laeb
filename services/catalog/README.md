# catalog service

**Owner (Wave):** A2  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Game metadata, media links, pricing, publishing state machine, festival discount overlay.

## User stories

US-09, US-10, US-11, US-12, US-13, US-14 (split is wallet), US-39 (price read)

## Endpoints (to implement)

- `POST /api/v1/catalog/games`
- `POST /api/v1/catalog/games/{id}/review`
- `POST /api/v1/catalog/games/{id}/suggest-price`
- `POST /api/v1/catalog/games/{id}/set-price`
- `POST /api/v1/catalog/games/{id}/publish`
- `GET  /api/v1/catalog/games`
- `GET  /api/v1/catalog/games/{id}`
- `GET  /api/v1/catalog/games/{id}/effective-price`

## Database

PostgreSQL `catalog`

## Events

- **Out:** game.published, game.price_changed
- **In:** festival.started, festival.ended

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/catalog/health` and `/health` green

## Local run

Service starts via `docker compose up catalog catalog-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
