# Phase 2 — 3-Day Implementation Plan

**Group 3 · Game Distribution Platform · Microservice Systems Design**
Methodology: Disciplined Agile Delivery — run as **3 one-day iterations** with a daily stand-up, a board, and a Definition of Done.

---

## 0. The rules we are actually graded on

Straight from `Project Definition.pdf` (§2.2 and the preamble). These constrain every decision below:

| Rule | Consequence for us |
|---|---|
| Phase 2 = **5 points** (Phase 1 = 3, total 8 mandatory + 1 bonus) | This is the biggest single deliverable of the course |
| **"Implementation must be done exactly per your Phase 1 document; conformance will definitely be checked"** | Every deviation must be back-ported into `Phase 1 Report.md` before we submit |
| "You may update the Phase 1 document if needed" | Deviating is *allowed* — silently deviating is not |
| **"Participation of all members is mandatory and in Phase 2 will be verified from the version-control history"** | Every person needs their own real, spread-out commits. One person merging everything = lost marks |
| "After Phase 1 grades, you must fix the issues raised against your design" | **Open item:** we need the Phase 1 feedback. Whatever the TA flagged gets fixed in the doc *and* in the code |
| Dockerizing is **mandatory**; correct Docker Compose use required | `git clone && docker compose up` must work on a clean machine |
| **+0.4** for Kubernetes | Stretch goal, Day 3 |
| **+0.6** for the competitive-advantage feature (TA-approved) | **Open item:** which of our three Phase 1 proposals did the TA approve? |

**Two things to confirm with the TA before Day 1 ends** — the Phase 1 feedback, and which bonus feature was approved.

---

## 1. Scope: 39 user stories → 11 services + gateway

Nothing in the requirements gets cut. What we *do* control is how much ceremony each service carries.

**Real domain complexity is concentrated in 5 places.** Everything else is CRUD:
1. Publishing state machine (US-09…US-13)
2. Purchase / gift / refund sagas + 70/30 split (US-14…US-18, US-36)
3. Append-only wallet ledger with idempotency (US-34…US-36)
4. The 5-minute matching engine (US-27, US-28)
5. CQRS projections + presence (US-06…US-08)

Protect those five. Everything else is a means of demonstrating them.

### Frontend

**We are not building an SPA.** The project definition never asks for one; this is an architecture course. We deliver:
- Swagger/OpenAPI per service, aggregated behind the gateway
- A Postman collection covering all 39 stories
- A `scripts/demo.sh` that drives the full happy path end-to-end with real HTTP calls

⚠️ Our Phase 1 container diagram shows a "Web / Mobile Client (SPA)". Either mark it explicitly as *out of scope for Phase 2 / consumer of the public API*, or build a single static HTML page on Day 3. **Pick one — do not leave the mismatch.**

---

## 2. Six decisions to lock in the first hour

These are cheap now and enormously expensive on Day 2. Write each one as a short ADR in `docs/adr/`.

**ADR-01 — One language, one framework, one service template.**
Recommendation: **Python + FastAPI**. Fastest to write, ~80 MB per container (we will run ~18 containers), Pydantic gives us free request validation and OpenAPI, and Clean Architecture maps onto it without ceremony.
*If your team is genuinely stronger in Java/TypeScript, use that instead* — but pick **one**. Six people debugging six toolchains on a 3-day clock is how this project fails. Note: Spring Boot × 11 services will likely exhaust a laptop's RAM; if you go Java, plan for it.

**ADR-02 — Database-per-service, logically.**
One Postgres container with **one database + one user per service** (no cross-service schema access, no shared tables, no cross-database joins). Same for one MongoDB container with a database per service. This satisfies the pattern exactly — nothing is shared — while saving ~5 containers of RAM. Document that scaling to separate instances is a Compose change, not a code change.

**ADR-03 — Drop Elasticsearch.**
Postgres full-text search for the store, MongoDB text indexes for forum search. Both give us US-33 and store search in a few lines. ES costs ~1 GB of RAM and a day of tuning for zero extra marks. Update §3.2 and §5.2 of the Phase 1 report.

**ADR-04 — REST + JSON internally, not gRPC.**
Our Phase 1 doc specifies gRPC for `Order → Catalog` and `Order → Wallet`. Proto tooling across 11 services is not worth it in 3 days. Go REST-internal, document the reasoning (and note that the synchronous-call boundary is unchanged — only the transport). *Optional Day-3 stretch:* add gRPC for the single `Wallet.debit` call as a showcase.

**ADR-05 — RabbitMQ topology.**
One topic exchange `platform.events`. Routing key = event name. One durable queue per consuming service. Transactional Outbox table in every producing service + a polling publisher in the shared kernel. Every consumer keeps a `processed_events(event_id UNIQUE)` table for idempotency.

**ADR-06 — Payment gateway is mocked.**
A tiny `mock-psp` container that accepts a charge request and calls back a webhook. **We never receive, log, or store card numbers** — that is NFR-04 and it is a talking point in the demo, not an omission.

---

## 3. Contracts to freeze before anyone writes business logic

P1 publishes these to `docs/contracts.md` in the first two hours. Nobody waits for anybody else once these exist — you code against the contract and stub the other side.

**JWT (HS256, shared secret via env; Identity signs, gateway + every service validate):**
```json
{ "sub": "<userId>", "username": "...", "roles": ["BASE_USER","DEVELOPER","SUPPORT","ADMIN"], "iat": 0, "exp": 0 }
```

**Headers:** `X-Correlation-Id` (gateway generates if absent, propagate everywhere, log it) · `Idempotency-Key` (required on every money-moving endpoint).

**Error envelope:** `{"error": {"code": "...", "message": "...", "correlationId": "..."}}`

**Routing:** `/api/v1/<service>/...` at the gateway.

**Ports:** gateway 8000 · identity 8001 · profile 8002 · catalog 8003 · order 8004 · wallet 8005 · review 8006 · trading 8007 · forum 8008 · festival 8009 · media 8010 · notification 8011

**Event catalog** (name → payload → consumers):

| Event | Payload | Consumed by |
|---|---|---|
| `user.registered` | userId, username, email | Profile |
| `user.role_granted` | userId, role, grantedBy | Notification |
| `game.published` | gameId, developerId, title, price | Forum (create board), Notification |
| `game.price_changed` | gameId, price | — |
| `order.game_purchased` | orderId, gameId, buyerId, recipientId, developerId, pricePaid, isGift | Profile, Review, Notification |
| `order.gift_sent` | orderId, gameId, senderId, recipientId, message | Notification |
| `order.refund_issued` | orderId, gameId, userId, amount | Profile, Notification |
| `trade.matched` | tradeId, itemId, buyerId, sellerId, price, qty | Wallet |
| `trade.payment_settled` | tradeId, ok | Trading |
| `trade.settled` | tradeId, … | Notification |
| `item.granted` | itemId, userId, qty | Notification |
| `forum.post_stats_changed` | postId, authorId, gameId, reactionCount, commentCount | Profile |
| `festival.started` / `festival.ended` | festivalId, entries[{gameId, discountPercent}], startsAt, endsAt | Catalog |
| `wallet.topped_up` | userId, amount, source | Notification |

**Repo layout:**
```
/services/<name>/app/{domain,application,adapters,infrastructure}   # Clean Architecture, per Phase 1 §3.1
/libs/shared-kernel/        # JWT middleware, RBAC, correlation ID, outbox, idempotency, event envelope
/gateway/
/deploy/{docker-compose.yml, .env.example, k8s/}
/docs/{adr/, contracts.md, traceability.md}
/scripts/{seed.py, demo.sh}
```

---

## 4. The six roles

Pairings follow **event and data adjacency**, so each person owns both sides of a contract wherever possible and cross-team chatter stays low.

| # | Role | Owns | Critical path? |
|---|---|---|---|
| **P1** | Platform & Integration Lead | Gateway, shared kernel, Compose, RabbitMQ, observability, CI, **Media**, **Notification**, docs, demo, K8s | **Yes — Day 1 AM blocks everyone** |
| **P2** | Identity & Profile | Identity, Profile (Redis presence, CQRS projections) | **Yes — JWT blocks everyone by Day 1 noon** |
| **P3** | Catalog & Forum | Catalog (publishing state machine, pricing, store search), Forum | Catalog blocks Order |
| **P4** | Order & Reviews | Order (purchase/gift/refund sagas, entitlements), Review | Depends on Catalog + Wallet |
| **P5** | Wallet & Festivals | Wallet (ledger, 70/30, top-up, gift cards, mock PSP), Festival | **Yes — Order and Trading both depend on it** |
| **P6** | Marketplace | Trading (items, grants, order book, 5-min matcher, settlement saga) | Hardest single service; mostly self-contained |

---

### P1 — Platform & Integration Lead

The only role that is *not* a domain. Front-loaded: the entire team is blocked until the skeleton exists, so P1's Day 1 morning is the highest-leverage work in the project.

**Deliverables**
- Monorepo skeleton + **service template** with the Clean Architecture folders already laid out, a working `/health`, `/ready`, `/metrics`, `/docs`, Dockerfile, and a DB migration hook. Everyone else copies this — it is the single biggest time-saver available.
- **Shared kernel library:** JWT validation middleware, `@requires_role(...)` decorator, correlation-ID propagation, structured JSON logger, outbox table + publisher loop, idempotency helper, event envelope, RabbitMQ connect/consume helpers with retries.
- **API Gateway:** routing to all 11 services, TLS termination config, JWT signature validation, rate limiting, request logging. (Traefik or a thin FastAPI reverse proxy — pick whichever you can configure fastest.)
- **`docker compose up` brings up everything:** Postgres, MongoDB, Redis, RabbitMQ, MinIO, mock-PSP, Prometheus, Grafana, gateway, 11 services — with `depends_on` + healthchecks so ordering is correct, and an init container that runs migrations and seeds.
- **Media Service** (~150 LOC): presigned PUT/GET against MinIO. Used by Forum, Catalog, and avatars.
- **Notification Service** (~150 LOC): pure broker consumer, writes to Mongo, exposes `GET /notifications?userId=`. Naturally P1's because P1 owns the broker helpers.
- **Observability:** Prometheus scrape config, a Grafana dashboard, and the **matching-cycle-duration alert** required by NFR-05/NFR-10.
- **Docs & submission:** back-port every ADR into `Phase 1 Report.md`, write the README, build `docs/traceability.md` (US → endpoint → service → test), record the demo.
- **Bonus:** K8s manifests (Deployment + Service + HPA per service) on Day 3.

*P1 must resist doing anyone else's domain work.* Their job on Days 2–3 is integration, unblocking, and the submission package.

---

### P2 — Identity & Profile

**Identity (Postgres)** — US-01…US-04
- Register (email/username + hashed password — bcrypt/argon2, never plaintext), login → JWT, refresh.
- Four roles: `BASE_USER`, `DEVELOPER`, `SUPPORT`, `ADMIN`. **Admin seeded at startup** (the spec says the admin account pre-exists).
- Role-upgrade request flow: user requests DEVELOPER/SUPPORT → admin grants/revokes → new token carries new roles.
- Publishes `user.registered`, `user.role_granted`.

**Profile (Postgres + Redis)** — US-05…US-08
- Name, avatar (URL from Media service).
- **Presence via Redis TTL keys:** `POST /presence/heartbeat` sets `presence:{userId}` with a 60 s TTL; online = key exists. Near-real-time, no polling other services (NFR-05).
- **Two CQRS read-model projections** — this is the pattern the whole architecture is justified on, so make it visibly correct:
  - `purchased_games` ← `order.game_purchased`, reversed on `order.refund_issued`
  - `top_posts` (top 5 across *all* forums by reactions + comments) ← `forum.post_stats_changed`
- Profile page reads **only its own DB**. No synchronous fan-out. Demonstrate this in the demo.

**Hard deadline: a working token issuer by Day 1, 14:00.** Everyone is blocked otherwise. Ship it, publish the contract, then move to Profile.

---

### P3 — Catalog & Forum

**Catalog (Postgres)** — US-09…US-13, US-33, US-39
- Game metadata, media links, developer ownership.
- **The publishing state machine** — enforce transitions in the domain layer, reject illegal ones with 409:
  `Submitted → UnderReview → {Rejected → Submitted | PriceSuggested} → PriceProposed → Published`
  Role-gated: only SUPPORT reviews/suggests/publishes; only the owning DEVELOPER sets the price. Keep an audit trail of transitions (NFR-07).
- **`GET /games/{id}/effective-price`** — the single source of truth for price, with the active festival discount applied. Order calls only this. Getting this boundary right is why festivals need zero changes in Order.
- Store browse/search/filter (Postgres FTS).
- Consumes `festival.started` / `festival.ended`; publishes `game.published`, `game.price_changed`.

**Forum (MongoDB)** — US-29…US-33
- Per-game board (auto-created on `game.published`), posts with media (via Media presigned URLs), comments, emoji reactions.
- Search within a game's forum via a Mongo text index.
- Publishes `forum.post_stats_changed` on every reaction/comment — this feeds P2's top-5 widget, so agree the payload with P2 on Day 1.

---

### P4 — Order & Reviews

**Order (Postgres)** — US-15…US-18, US-36. The saga orchestrator; the most interesting service to demo.
- **Purchase saga:** `GET effective-price` (Catalog) → `debit` with an `Idempotency-Key` (Wallet, which performs the 70/30 split in one ACID tx) → create Order + Entitlement in a local tx **with the outbox row in the same tx** → publish `order.game_purchased`.
- **Compensation:** if entitlement creation fails, issue `credit(buyer, P)`. Implement it and **demo it deliberately** with a forced failure — examiners look for this.
- **Gift (US-16, US-17):** total = `P` normally; `P × 1.002` when a message is attached (**0.2% surcharge — see §7, our doc currently contradicts itself on this**). Recipient gets the entitlement, sender pays.
- **Refund (US-18):** reject if `now - purchasedAt > 12h`. Revoke entitlement, publish `order.refund_issued`, Wallet writes the reversing ledger entries (buyer P+, developer 0.7P−, platform 0.3P−).
- Library/entitlement query endpoints.

**Review (MongoDB)** — US-19…US-22
- Like/dislike is **mandatory** *and* explanatory text is **mandatory** — enforce both in the domain layer.
- **Ownership check reads a local projection built from `order.game_purchased`** — no synchronous call to Order. This is the loose-coupling decision from Phase 1 §3.2; implement it that way, not with an HTTP call.
- Emoji reactions on reviews.

Same owner for both, because P4 controls both the producer and the consumer of the ownership contract.

---

### P5 — Wallet & Festivals

**Wallet (Postgres)** — US-14, US-34…US-36. Strongest ACID requirements in the system; treat every endpoint as if real money moves.
- Balances + **append-only double-entry ledger** (`INSERT` only, never `UPDATE`/`DELETE` — NFR-07). Corrections are reversing entries.
- **Idempotent `debit` / `credit`**: `Idempotency-Key` unique constraint; a replayed key returns the original result rather than moving money twice.
- **70/30 split in a single transaction:** buyer −P, developer +0.7P, platform +0.3P. One `BEGIN`/`COMMIT`. Unit-test the arithmetic and the rounding rule.
- Top-up via the **mock PSP** (redirect → webhook callback → credit). Card data never touches us.
- **Gift cards:** single-use codes, redemption atomic under concurrency (test it).
- Consumes `trade.matched` → settles buyer→seller at the seller's price → publishes `trade.payment_settled`.
- `GET /ledger?userId=` for the audit-trail demo.

**Festival (Postgres)** — US-37, US-38, US-39
- Create a festival, add games with a discount percent (**0–100%; 100% = free is explicitly allowed**).
- **Developer approval required per game** before the discount goes live (US-38).
- Scheduled start/end → publishes `festival.started` / `festival.ended` → Catalog applies the overlay. Order needs no changes at all — say this out loud in the demo, it demonstrates NFR-08.

---

### P6 — Marketplace (Trading)

One service, but the hardest one. US-23…US-28.

- **Item definitions** by developer, no default price (US-23).
- **Distribution (US-24):** grant to an arbitrary *or random* set of players, in arbitrary *or random* quantities. Both modes; expose them as explicit API parameters.
- **Inventory:** per-user item holdings.
- **Order book:** buy orders (any price) and sell orders (owner only, ownership verified and quantity reserved at order time).
- **The 5-minute matching engine** — the centerpiece:
  - Scheduler tick every 5 min, guarded by a **Redis distributed lock** so cycles cannot overlap (NFR-05: overlap = double-processed orders).
  - Load open orders per item: buys DESC, sells ASC.
  - Rule (a): exact equal prices → match at that price.
  - Rule (b): buy > sell → pair by **minimum difference**, settle at the **seller's (lower) price**.
  - Row-level locking during the cycle; publish `trade.matched` per match.
  - **Emit a cycle-duration metric** and alert if it approaches 5 minutes.
- **Settlement saga (US-28, atomicity):** `trade.matched` → Wallet moves funds → `trade.payment_settled` → transfer item ownership. On failure, compensate and reopen the orders. Nothing is lost, ever — build a test that proves it.
- Unit-test the matcher against a fixed order book. It is the easiest thing in the project to get subtly wrong and the easiest to demonstrate convincingly when right.

---

## 5. Three-day schedule

### Day 0 — pre-flight (2–3 hours, whole team, tonight if possible)

Do not spend Day 1 morning on this.

1. Agree ADR-01…ADR-06 (§2). 20 minutes, then stop debating.
2. P1 pushes the skeleton: repo layout, service template, shared kernel stub, Compose with **infrastructure only** (Postgres, Mongo, Redis, RabbitMQ, MinIO), Makefile.
3. P1 publishes `docs/contracts.md` (§3). Everyone reviews it in the same sitting.
4. Create a board with one issue per user story, labelled by owner. This is your DAD evidence — screenshot it at the end of each day.
5. **Everyone clones and gets `docker compose up` green on their own machine.** Environment problems discovered on Day 2 are fatal.

### Day 1 — skeletons and vertical slices

| | |
|---|---|
| **AM** | P1: gateway routing + Compose with all 11 (stub) services green. **P2: Identity shipped by 14:00 — hard deadline.** P3–P6: scaffold from the template, write DB schema + migrations, define domain entities, stub every endpoint as 501, get into Compose with a green healthcheck. |
| **PM** | Core logic of each primary service against its **own DB only** — no cross-service calls yet. Catalog: full state machine. Wallet: ledger + idempotent debit/credit + 70/30. Order: order + entitlement with a stubbed wallet. Trading: items, grants, order book. Profile: CRUD + presence. Forum: posts + comments. |
| **Stand-up** | 15 min, end of day. Anything red gets reassigned tonight, not tomorrow. |

**🏁 Milestone M1:** `docker compose up` starts all services · gateway routes to all · all `/health` green · Identity issues valid JWTs · every service validates JWT and enforces RBAC.

### Day 2 — integration day (the one that decides the grade)

| | |
|---|---|
| **AM** | Turn on the broker. Outbox publishers + idempotent consumers live. **Purchase saga end-to-end**: Order → Catalog price → Wallet debit + 70/30 → entitlement → `order.game_purchased` → Profile projection + Notification. Trading's first real matching cycle with settlement. |
| **PM** | Everything else through the broker: gift (+0.2%), refund (12h + reversal), reviews with projection-based ownership, forum stats → top-5 widget, festival → discount → effective price, media presigned uploads used by Forum and Catalog. P1 starts `scripts/seed.py` + `demo.sh`. |
| **Stand-up** | Walk the demo script together. Every gap is a Day 3 AM task. |

**🏁 Milestone M2:** every user story **US-01 … US-39** demonstrable through the API. If a story cannot be demoed by end of Day 2, escalate it now — Day 3 is not spare capacity.

### Day 3 — hardening, NFRs, submission

| | |
|---|---|
| **AM** | The NFRs *are* graded. Idempotency replay tests · saga compensation tests (forced failures) · circuit breakers + timeouts on every sync call (NFR-02) · gateway rate limiting · correlation IDs end-to-end · Prometheus dashboards + the matching-cycle alert · seed data that makes the demo tell a story. |
| **PM** | **Submission package.** Back-port every ADR into `Phase 1 Report.md` · README with architecture + run instructions · `docs/traceability.md` (US → endpoint → service → test) · K8s manifests (bonus) · **clean clone on a second machine, `docker compose up`, run `demo.sh`** · record the demo · tag the release. |

**🏁 Milestone M3:** fresh clone → one command → demo passes → docs match code.

---

## 6. Definition of Done (per service — no exceptions)

- [ ] `/health`, `/ready`, `/metrics`, `/docs` (OpenAPI)
- [ ] Dockerfile; in Compose; starts clean from an empty volume; migrations run on boot
- [ ] JWT validated + RBAC enforced on every protected route
- [ ] Structured JSON logs carrying `X-Correlation-Id`
- [ ] Outbox row written **in the same transaction** as any state change others care about
- [ ] Consumers idempotent (`processed_events` unique constraint)
- [ ] ≥1 unit test on the domain rule it owns (70/30 · 12-hour window · 0.2% surcharge · matcher · state machine)
- [ ] README section: endpoints, events in/out, env vars
- [ ] Its user stories are in `demo.sh`

---

## 7. Phase 1 document fixes (do this before implementing)

**🔴 Blocking contradiction — the gift surcharge.** The project definition says **0.2%** of the game price (`۰.۲ درصد`). Our report says 0.2% in US-17, but §3.2 (Order Service row) and §5.1 both say **"200% surcharge = 3× total"**. Those cannot both ship.
**The correct value is 0.2%.** Fix §3.2 and §5.1 before P4 writes the gift flow, or we implement the wrong requirement and lose marks on both conformance *and* correctness.

**Also to update in `Phase 1 Report.md`:**
- §3.2 / §5.2 — remove Elasticsearch (ADR-03), remove gRPC (ADR-04)
- §3.2 — Publishing Workflow merged into Catalog (§5.3 already anticipates this; state it as done)
- §4.2 — resolve the SPA question (§1 above)
- §3.3 — note the logical database-per-service arrangement (ADR-02)
- §6 — mark which bonus feature the TA approved and that it is implemented
- **Whatever the Phase 1 grading feedback raised** — mandatory per the project definition

Add a short changelog section listing each change and its reason. That is exactly what "conformance checking" looks for, and it turns deviations from a liability into evidence of engineering judgement.

---

## 8. Process rules — these carry marks

1. **Everyone commits under their own identity, every day.** The definition says participation is verified from version-control history. Six contributors with commits spread across all three days. No "final merge by one person."
2. **Branch per person** (`feat/wallet`, `feat/trading`, …), PR into `main`, one teammate reviews. PRs are also your DAD evidence.
3. **Small, frequent, conventional commits** (`feat(wallet): 70/30 split in single tx`). A single 5,000-line commit on Day 3 looks exactly like what it looks like.
4. **Never break `main`.** If `docker compose up` is red on `main`, that is the whole team's top priority.
5. **Daily stand-up, 15 minutes.** Blockers only. Record the notes — they go in the report as methodology evidence.
6. **Contracts change only by announcement.** Change `docs/contracts.md` first, tell the affected owner, then code.

---

## 9. Bonus points (+1.0)

- **+0.4 Kubernetes** — one Deployment + Service per microservice, ConfigMaps/Secrets for env, one HPA (Catalog or Order, justified by NFR-01: "scale the store independently during festivals"). Day 3 PM. Only start once M3 is safe.
- **+0.6 Competitive-advantage feature** — must be the TA-approved one. If the choice is still open, **§6.3 Achievements** is the cheapest by a wide margin: a pure event consumer + Postgres, zero changes to existing services, and it *demonstrates* NFR-08 (a new service plugs into the event stream and touches nothing else). §6.2 MarketAnalytics is the natural second choice and pairs with P6's `trade.matched` stream.

---

## 10. Risks and the cut list

| Risk | Mitigation |
|---|---|
| Day 1 skeleton slips → six people idle | Do Day 0 tonight. P1 starts before anyone else. |
| Identity late → nothing testable | Hard 14:00 Day 1 deadline; ship auth first, Profile second |
| RAM exhaustion (~18 containers) | ADR-02 + ADR-03; set container memory limits; test on the weakest laptop early |
| Integration all lands on Day 2 | Contract-first + stubs from Day 1: nobody blocks on anyone |
| Matching engine overruns the 5-min window | Redis lock from the start; metric on cycle duration from the start |
| Docs drift from code | P1 writes ADRs *as decisions are made*, not on Day 3 |

**If we fall behind, cut in this order** — and record each cut in the report:
1. Kubernetes manifests
2. Grafana dashboards (keep `/metrics` — the endpoint is what proves NFR-10)
3. Media service (store URLs / a shared volume instead)
4. Notification service (log-only sink)
5. Emoji reactions on *reviews* (keep them on forum posts)
6. Festival folded into Catalog (update the doc if so)

**Never cut, at any cost:** purchase + 70/30 split + 12-hour refund · the 5-minute matching engine · RBAC across all four roles · `docker compose up` · document ↔ implementation conformance.

---

## 11. Do this in the next 90 minutes

1. **Ali** → ask the TA for the Phase 1 feedback and confirm the approved bonus feature.
2. **Whole team** → 20-minute call: assign P1–P6, agree ADR-01…ADR-06.
3. **P1** → push the skeleton + `docs/contracts.md`.
4. **Everyone** → clone, `docker compose up`, and **make your first commit today**. The clock on the version-control history starts now.
