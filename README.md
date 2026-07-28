# Laeb — Game Distribution Platform

Repository for the **Microservice Systems Engineering** course project (Group 3).  
Phase 1 architecture lives in [`Phase 1 Report.md`](Phase%201%20Report.md). Phase 2 plan lives in [`Phase 2 Plan.md`](Phase%202%20Plan.md).

This branch (`feat/a1-platform`) delivers **Wave A / Role A1 — Platform & Foundation**: a runnable Docker Compose stack, shared kernel, eleven service stubs, frozen contracts, and handoff docs so A2/A3 and Wave B can start without waiting.

---

## Quick start

```bash
git clone https://github.com/Almolia/Laeb.git
cd Laeb
git checkout feat/a1-platform
cp .env.example .env
make up
# wait ~45s for healthchecks
bash scripts/smoke.sh
```

| URL | Purpose |
|---|---|
| http://localhost:8000 | API Gateway (Traefik) |
| http://localhost:8080 | Traefik dashboard |
| http://localhost:15672 | RabbitMQ management (`guest` / `guest`) |
| http://localhost:9001 | MinIO console |
| http://localhost:9090 | Prometheus |
| http://localhost:3000 | Grafana (`admin` / `admin`) |
| http://localhost:8020/docs | mock payment gateway |

Per-service OpenAPI: `http://localhost:800N/docs` (identity=8001 … notification=8011).

If `docker compose build` fails with Docker Hub **Forbidden**, configure a registry mirror (common on restricted networks) and retry.

---

## What A1 built (this PR / branch)

### 1. Repository skeleton

- `.gitignore`, `.env.example` (JWT, Postgres, Mongo, Redis, RabbitMQ, MinIO, admin seed vars)
- Layout: `libs/`, `services/`, `infra/`, `mock-psp/`, `scripts/`, `docs/adr/`, `gateway/`
- Branch: `feat/a1-platform`

### 2. Shared kernel (`libs/shared_kernel`)

Single dependency set and library used by **every** service:

| Module | Role |
|---|---|
| `config.py` | pydantic-settings from env |
| `logging.py` | JSON logs + `X-Correlation-Id` context |
| `errors.py` | unified error envelope |
| `auth.py` | JWT issue/validate, RBAC helpers (`BASE_USER` / `DEVELOPER` / `SUPPORT` / `ADMIN`) |
| `health.py` | `/health`, `/ready` |
| `app.py` | FastAPI factory + Prometheus `/metrics` |
| `db.py` | sync SQLAlchemy engine/session |
| `events.py` | RabbitMQ topic exchange publish/consume |
| `outbox.py` | Transactional Outbox (NFR-06) |
| `inbox.py` | idempotent event claim |
| `idempotency.py` | money-endpoint idempotency keys |
| `money.py` | integer minor units, 70/30 split, 0.2% gift surcharge, discounts |

### 3. Service template + 11 stubs

- Template: `services/_template/` (Dockerfile builds from **repo root** so `libs/` is available)
- Scaffolded services (Clean Architecture folders + api + worker containers):

  `identity`, `profile`, `catalog`, `order`, `wallet`, `review`, `trading`, `forum`, `festival`, `media`, `notification`

- Each exposes:
  - `/health` — Docker healthcheck
  - `/api/v1/<service>/health` — gateway smoke
  - `/api/v1/<service>/ping` — stub ping
- Domain logic is **intentionally stubbed**; Wave A2/A3 and Wave B fill it in (see each `services/<name>/README.md`).

### 4. Docker Compose infrastructure

| Component | Notes |
|---|---|
| PostgreSQL 16 | One DB + user per relational service (`infra/postgres/init.sql`) — ADR-02 |
| MongoDB 7 | `review`, `forum`, `notification` |
| Redis 7 | presence / order-book cache |
| RabbitMQ 3.13 | exchange `platform.events` |
| MinIO | media object storage |
| Traefik v3 | gateway on `:8000`, path prefix `/api/v1/<service>`, rate limit |
| Prometheus + Grafana | scrape all services; overview dashboard; alert doc for match-cycle SLA |
| mock-psp | fake bank gateway on `:8020` (no card data in our services) |

`Makefile` targets: `up`, `down`, `fresh`, `smoke`, `seed`, `demo`, `logs`, `test`.

### 5. Frozen contracts & ADRs

- [`docs/contracts.md`](docs/contracts.md) — money rules, JWT claims, headers, error envelope, ports, **event catalog**
- [`docs/adr/`](docs/adr/) — ADR-01…06 (Python/FastAPI, DB-per-service, drop ES, REST internal, RabbitMQ, mock PSP)

### 6. Ops scripts & CI

| Path | Purpose |
|---|---|
| `scripts/smoke.sh` | curl all 11 services through the gateway |
| `scripts/seed.py` | idempotent seed skeleton (domain TODOs for A2/A3/B*) |
| `scripts/demo.sh` | section headers for all 39 user stories |
| `scripts/scaffold.sh` | recreate service stubs from template |
| `.github/workflows/ci.yml` | build + compose up + smoke on push/PR |

### 7. Handoff for the rest of the team

- [`docs/HANDOFF.md`](docs/HANDOFF.md) — runbook, repo map, gotchas, owner table
- Per-service README with user-story IDs, endpoints, events in/out, TODO checklist

---

## Architecture sketch

```
Client → Traefik (:8000)
           ├─ identity / profile / catalog / order / wallet / …
           └─ each service: api container + worker container
                  ├─ Postgres | Mongo | Redis | MinIO
                  └─ RabbitMQ (outbox → events → inbox)
Wallet ↔ mock-psp (:8020)
Prometheus ← /metrics on each service
```

Publishing workflow is **merged into Catalog** (as Phase 1 allowed for Phase 2). Internal sync calls are **REST**, not gRPC (ADR-04). Elasticsearch is **not** in Compose (ADR-03).

---

## What is still TODO (not A1)

| Owner | Work |
|---|---|
| **A2** | Identity + Catalog domain (register/login/roles, publish state machine) |
| **A3** | Wallet ledger, top-up via mock-psp, gift cards, 70/30 |
| **B1** | Order purchase/gift/refund sagas + Festival |
| **B2** | Trading matching engine + `trading_match_cycle_duration_seconds` |
| **B3** | Profile projections, Review, Forum, Media |
| Shared | Notification consumers, fill `demo.sh` / `seed.py` |

---

## Commit history on this branch (A1)

1. `chore: repository skeleton and environment template`
2. `feat(platform): shared kernel and service template`
3. `feat(platform): docker-compose infrastructure (…) `
4. `feat(platform): messaging, outbox, inbox, idempotency and money primitives`
5. `feat(platform): scaffold 11 services with compose api/worker and Makefile`
6. `docs: freeze platform contracts and ADRs`
7. `feat(platform): smoke scripts, mock-psp, prometheus and grafana`
8. `docs: handoff guide, per-service READMEs and CI workflow`
9. cleanup + this README

---

## Docs index

| Doc | Contents |
|---|---|
| [Phase 1 Report.md](Phase%201%20Report.md) | Requirements, architecture, diagrams |
| [Phase 2 Plan.md](Phase%202%20Plan.md) | 3-day implementation plan & roles |
| [docs/contracts.md](docs/contracts.md) | Frozen API / event contracts |
| [docs/HANDOFF.md](docs/HANDOFF.md) | Day-2 handoff for Wave B |
| [docs/adr/](docs/adr/) | Architecture decisions |
| [Project Definition.pdf](Project%20Definition.pdf) | Course brief |
