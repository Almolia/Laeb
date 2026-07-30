# Trading service — B2 Marketplace

**Branch:** `feat/B2-marketplace-festivals`  
**Port:** `8007` through Docker Compose / `/api/v1/trading` through the gateway  
**Stories:** US-23…US-28

## Scope

Trading owns in-game item definitions, grants, player holdings, buy/sell orders,
the five-minute matching cycle, and the item side of the Wallet settlement saga.
Items intentionally have **no default price**; every market participant chooses a
price per order.

## Matching rule

`app/domain/matching.py` is a pure function. A pair is eligible when:

```text
buy.price_minor >= sell.price_minor
```

At every round, the engine chooses the eligible pair with the minimum
`buy.price_minor - sell.price_minor`. Exact-price matches have difference zero,
so they naturally win without a separate rule. Ties use oldest buy, then oldest
sell. Self-trades are skipped and partial fills are supported.

The trade price is always the seller's price. A buy at `150` matched with a sell
at `100` settles at `100`.

## Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/games/{gameId}/items` | DEVELOPER and game owner |
| GET | `/games/{gameId}/items` | public |
| GET | `/items/{id}` | public |
| POST | `/items/{id}/grants` | DEVELOPER and item owner |
| GET | `/inventory/me` | any authenticated user |
| GET | `/inventory/{userId}` | any authenticated user |
| POST | `/orders/buy` | any authenticated user |
| POST | `/orders/sell` | any authenticated user |
| GET | `/orders/me?status=` | any authenticated user |
| DELETE | `/orders/{id}` | owner |
| GET | `/items/{id}/orderbook` | public |
| GET | `/trades?itemId=&limit=` | any authenticated user |
| GET | `/match-cycles?limit=20` | any authenticated user |
| POST | `/internal/run-match-cycle` | ADMIN |

## Grants

`POST /items/{id}/grants` supports all four required combinations:

- EXPLICIT recipients + FIXED quantity
- EXPLICIT recipients + RANDOM quantity
- RANDOM recipients + FIXED quantity
- RANDOM recipients + RANDOM quantity

An optional `seed` makes random selection reproducible. Every recipient update
and its `item.granted` outbox message are committed in the same transaction.

The current Identity implementation originally required `GET /users?ids=...`.
B2 adds a backward-compatible no-parameter form, `GET /users`, so random grants
can obtain the complete candidate list.

## Reservation and cancellation

A sell order locks its holding row and reserves the requested quantity at order
creation. Available quantity is:

```text
holding.quantity - holding.reserved
```

Insufficient inventory returns `409 INSUFFICIENT_ITEMS`. A cancellation is
allowed only for OPEN or PARTIAL orders and releases only the unmatched
remainder. Buy orders do not reserve Wallet funds; Wallet validates funds when
the match is settled.

## Five-minute cycle

Both APScheduler and the manual demo endpoint call
`run_cycle_with_lock()`. The entry point acquires Redis key
`trading:match-cycle:lock` with a 280-second TTL. This prevents overlapping
cycles from processing the same orders twice while allowing recovery after a
crashed worker.

For each item, open rows are loaded in deterministic ID order with
`FOR UPDATE`, converted to domain `BookOrder` objects, matched, then persisted in
one transaction per item. Each result creates a `PENDING_PAYMENT` trade and a
`trade.matched` outbox event.

Cycle history is stored in `match_cycles`. The worker exposes
`trading_match_cycle_duration_seconds` on port `9107`; Prometheus is configured
to scrape `trading-worker:9107`.

## Settlement saga

```text
trading --trade.matched--> wallet
wallet --trade.payment_settled--> trading
```

Success:

1. lock trade and holdings;
2. subtract item quantity and reservation from seller;
3. add item quantity to buyer;
4. mark trade SETTLED;
5. emit `trade.settled` through the outbox.

Failure:

1. move no item;
2. release the failed seller reservation;
3. reopen the buy quantity;
4. remove/cancel only the failed slice of the sell order;
5. mark trade FAILED.

`processed_events` makes the consumer idempotent.

## Environment

```text
DATABASE_URL=postgresql+psycopg://trading_user:servicepass@postgres:5432/trading
REDIS_URL=redis://redis:6379
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
CATALOG_URL=http://catalog:8000/api/v1/catalog
IDENTITY_URL=http://identity:8000/api/v1/identity
```

The last two values have those Docker-network defaults and can be overridden for
local execution.

## Run and test

```bash
docker compose up --build trading trading-worker
PYTHONPATH=services/trading pytest services/trading/tests -q
```

Manual cycle:

```bash
curl -X POST http://localhost:8000/api/v1/trading/internal/run-match-cycle \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Complexity and future optimization

The pure matcher scans all eligible buy/sell pairs for each produced match. It
is intentionally straightforward and deterministic for the Phase 2 demo scale.
Its worst-case cost is higher than a sorted two-pointer or heap-based book; that
optimization is future work. The cycle histogram and `match_cycles` table make
the current behavior measurable against NFR-05.
