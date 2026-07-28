# media service

**Owner (Wave):** B3  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Uploads, virus-scan hook stub, thumbnails, pre-signed MinIO URLs.

## User stories

US-09 (binaries), US-30 (forum media), US-05 (avatar)

## Endpoints (to implement)

- `POST /api/v1/media/upload-url`
- `POST /api/v1/media/complete`
- `GET  /api/v1/media/{id}`

## Database

MinIO bucket `media` (no relational DB)

## Events

- **Out:** (optional media.processed)
- **In:** (thumbnail jobs via queue)

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/media/health` and `/health` green

## Local run

Service starts via `docker compose up media media-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
