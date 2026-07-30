# Festival service — B2 Discounts

**Branch:** `feat/B2-marketplace-festivals`  
**Port:** `8009` through Docker Compose / `/api/v1/festival` through the gateway  
**Stories:** US-37, US-38, US-39 discount half

## Scope

Festival manages festival windows and game discount proposals. Catalog remains
the owner of game prices. Festival only emits lifecycle events, and Catalog
applies/removes its local discount overlay. Order and Wallet require no festival
code changes.

## Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/festivals` | SUPPORT or ADMIN |
| POST | `/festivals/{id}/entries` | SUPPORT or ADMIN |
| GET | `/festivals?status=ACTIVE` | public |
| GET | `/festivals/{id}` | public |
| GET | `/festivals/entries/pending` | DEVELOPER |
| POST | `/festivals/{id}/entries/{gameId}/approve` | owning DEVELOPER |
| POST | `/festivals/{id}/entries/{gameId}/reject` | owning DEVELOPER |
| POST | `/internal/festivals/{id}/activate` | ADMIN |

## Ownership and discounts

When an entry is added, Festival calls Catalog:

```text
GET /api/v1/catalog/games/internal/{gameId}/summary
```

The returned `developerId` is stored on the entry. Only that developer may
approve or reject it. Discounts are validated in the inclusive range 0…100;
100% is legal and makes the effective Catalog price zero.

## Lifecycle

Festivals start as DRAFT. A one-minute APScheduler job:

- activates DRAFT festivals whose `starts_at` has passed;
- ends ACTIVE festivals whose `ends_at` has passed.

The manual ADMIN activation endpoint calls the same application function used
by the scheduler, so the demo does not need to wait.

On activation, only APPROVED entries are included:

```json
{
  "festivalId": "...",
  "startsAt": "...",
  "endsAt": "...",
  "entries": [{"gameId": "...", "discountPercent": 30}]
}
```

Pending and rejected entries stay in the database but are excluded from
`festival.started`. Ending emits `festival.ended` with only `festivalId`.
Both events are written through the transactional outbox.

## Event-driven decoupling demonstration

1. query Catalog effective price and observe `discountPercent: 0`;
2. create a festival and add a game;
3. let the owning developer approve it;
4. activate the festival manually;
5. wait for the Catalog consumer;
6. query effective price again and observe the discounted amount;
7. purchase through Order without modifying Order or Wallet.

This round trip demonstrates NFR-08: a new service changes store pricing through
events while existing purchase services remain unchanged.

## Environment

```text
DATABASE_URL=postgresql+psycopg://festival_user:servicepass@postgres:5432/festival
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
CATALOG_URL=http://catalog:8000/api/v1/catalog
```

## Run and test

```bash
docker compose up --build festival festival-worker catalog catalog-worker
PYTHONPATH=services/festival pytest services/festival/tests -q
```

Manual activation:

```bash
curl -X POST \
  http://localhost:8000/api/v1/festival/internal/festivals/$FESTIVAL_ID/activate \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```
