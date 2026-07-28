# HANDOFF — Laeb Platform (A1)

For someone who has never opened this repository.

## 1. Run it in 5 minutes

```bash
git clone https://github.com/Almolia/Laeb.git
cd Laeb
git checkout feat/a1-platform   # until merged to main
cp .env.example .env
make up
# wait ~45s for healthchecks
bash scripts/smoke.sh
python scripts/seed.py
```

Expected: smoke prints `OK` for all 11 services through the gateway on port **8000**.

Get a token (once Identity is implemented by A2):

```bash
curl -s http://localhost:8000/api/v1/identity/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

## 2. What exists

| Service | Status | Wave B owner | Port | Database | README |
|---|---|---|---|---|---|
| identity | stub (A2 builds) | A2 | 8001 | Postgres `identity` | [README](../services/identity/README.md) |
| profile | stub | B3 | 8002 | Postgres `profile` + Redis | [README](../services/profile/README.md) |
| catalog | stub (A2 builds) | A2 | 8003 | Postgres `catalog` | [README](../services/catalog/README.md) |
| order | stub | B1 | 8004 | Postgres `orders` | [README](../services/order/README.md) |
| wallet | stub (A3 builds) | A3 | 8005 | Postgres `wallet` | [README](../services/wallet/README.md) |
| review | stub | B3 | 8006 | Mongo `review` | [README](../services/review/README.md) |
| trading | stub | B2 | 8007 | Postgres `trading` + Redis | [README](../services/trading/README.md) |
| forum | stub | B3 | 8008 | Mongo `forum` | [README](../services/forum/README.md) |
| festival | stub | B1 | 8009 | Postgres `festival` | [README](../services/festival/README.md) |
| media | stub | B3 | 8010 | MinIO | [README](../services/media/README.md) |
| notification | stub | any | 8011 | Mongo `notification` | [README](../services/notification/README.md) |

Infrastructure: Postgres, Mongo, Redis, RabbitMQ, MinIO, Traefik gateway, Prometheus, Grafana, mock-psp.

## 3. How to build a service (walkthrough shape)

Use Catalog as the reference shape once A2 lands real code. Pattern:

1. **Domain** — pure rules in `app/domain/` (no FastAPI, no SQLAlchemy imports)
2. **Application** — use-cases / sagas in `app/application/`
3. **Adapters** — HTTP routers in `app/adapters/`
4. **Infrastructure** — ORM models, repositories in `app/infrastructure/`
5. **Publish events** — `outbox.enqueue(session, event_name, payload, producer)` inside the same DB transaction as the state change; worker runs `outbox.run_publisher()`
6. **Consume events** — in `worker.py`, `events.consume("q.<service>", [...], handler)`; start with `inbox.claim(session, env.eventId)`
7. **Migrations** — Alembic under `services/<name>/migrations` when you add Postgres tables

Router prefix **must** be `/api/v1/<service>` (see `docs/contracts.md`).

## 4. Where things live

| Path | Purpose |
|---|---|
| `libs/shared_kernel/` | Auth, DB, events, outbox/inbox, money, logging |
| `services/_template/` | Copy source for new services |
| `services/<name>/` | One microservice |
| `mock-psp/` | Fake payment gateway |
| `infra/` | Postgres init, Prometheus, Grafana, alerts doc |
| `docs/contracts.md` | **Frozen** API/event contracts |
| `docs/adr/` | Architecture decision records |
| `scripts/` | scaffold, smoke, seed, demo |
| `docker-compose.yml` | Full stack |
| `Makefile` | `up` / `down` / `fresh` / `smoke` |

## 5. Gotchas

- **Build context is the repo root**, not the service folder (`dockerfile: services/x/Dockerfile`, `context: .`)
- DB name is **`orders`**, not `order` (SQL reserved word)
- Sync SQLAlchemy on purpose — do not switch to async
- Money is **integer minor units** — never float
- `make fresh` **wipes volumes**
- Traefik rate-limit middleware is defined on the identity container; others reference `ratelimit@docker`
- `/health` (ops) vs `/api/v1/<service>/health` (gateway smoke)

## 6. Known gaps / TODOs

- Identity / Catalog / Wallet domain logic — **A2 / A3**
- Order / Festival sagas — **B1**
- Trading matching engine + metric `trading_match_cycle_duration_seconds` — **B2**
- Profile projections, Review, Forum, Media — **B3**
- Notification consumers — anyone after events exist
- `scripts/demo.sh` sections are headers only until Wave B
- Docker Hub may be blocked on some networks (Iran) — use a mirror if `docker compose build` fails with Forbidden
- Walkthrough video link — TBD (record and paste here)

## 7. Useful URLs

| URL | What |
|---|---|
| http://localhost:8000 | API gateway |
| http://localhost:8080 | Traefik dashboard |
| http://localhost:15672 | RabbitMQ (guest/guest) |
| http://localhost:9001 | MinIO console |
| http://localhost:9090 | Prometheus |
| http://localhost:3000 | Grafana (admin/admin) |
| http://localhost:8020/docs | mock-psp |
| http://localhost:8001/docs | identity OpenAPI (direct) |
| http://localhost:8000/api/v1/identity/docs | identity via gateway (if routed) |

Per-service docs are also on `:800N/docs` when running.
