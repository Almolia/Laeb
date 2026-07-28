# catalog service

**Owner (Wave):** A2  
**Status:** implemented

## Purpose

Game publishing state machine (US-09…US-13), store FTS search (US-33), festival price overlay for browsing (US-39).

## User stories

US-09, US-10, US-11, US-12, US-13, US-33, US-39

## Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/catalog/games` | DEVELOPER |
| GET | `/api/v1/catalog/games` | public (`?q=&genre=&state=Published`) |
| GET | `/api/v1/catalog/games/mine` | DEVELOPER |
| GET | `/api/v1/catalog/games/{id}` | public |
| GET | `/api/v1/catalog/games/{id}/history` | SUPPORT or owner |
| POST | `/api/v1/catalog/games/{id}/review/start` | SUPPORT |
| POST | `/api/v1/catalog/games/{id}/review/reject` | SUPPORT |
| POST | `/api/v1/catalog/games/{id}/review/approve` | SUPPORT |
| POST | `/api/v1/catalog/games/{id}/price` | DEVELOPER (owner) |
| POST | `/api/v1/catalog/games/{id}/publish` | SUPPORT |
| POST | `/api/v1/catalog/games/{id}/resubmit` | DEVELOPER (owner) |
| GET | `/api/v1/catalog/games/{id}/effective-price` | public |
| GET | `/api/v1/catalog/games/internal/{id}/summary` | any |

## Database

PostgreSQL `catalog` — `games` (GIN `search_vector`), `game_state_history`, `active_discounts`, `outbox`, `processed_events`.

## Events

- **Out:** `game.published`, `game.price_changed`
- **In:** `festival.started`, `festival.ended` (queue `q.catalog`)

## For B1 (Order service)

Copy-paste:

```bash
curl -s http://localhost:8000/api/v1/catalog/games/$GID/effective-price
```

Response shape:

```json
{
  "gameId": "...",
  "basePriceMinor": 500000,
  "discountPercent": 20,
  "effectivePriceMinor": 400000,
  "festivalId": "...",
  "isPublished": true
}
```

**If `isPublished` is false, refuse the purchase with `GAME_NOT_PUBLISHED`.**

## Festival consumer manual test

See [FESTIVAL_MANUAL_TEST.md](FESTIVAL_MANUAL_TEST.md). Publish `festival.started` from RabbitMQ UI to verify discounts without Festival service.

## Tests

```bash
docker compose exec catalog pytest -q /app/tests
```

## Decisions I made

- Publishing workflow lives inside Catalog (no separate Publishing Workflow service).
- Illegal transitions → 409; wrong role / non-owner → 403.
- 100% discount → `effectivePriceMinor: 0` is legal.

## Known gaps

- Media binaries go through Media service; Catalog only stores URL strings.
- Festival service (B1/B2) produces events; Catalog only consumes.
