# forum service

**Owner (Wave):** B3  
**Status:** stub (healthy) — implement domain logic here

## Purpose

Per-game boards, posts with media refs, comments, emoji feedback, search.

## User stories

US-29, US-30, US-31, US-32, US-33

## Endpoints (to implement)

- `GET  /api/v1/forum/games/{gameId}/posts`
- `POST /api/v1/forum/games/{gameId}/posts`
- `POST /api/v1/forum/posts/{id}/comments`
- `POST /api/v1/forum/posts/{id}/reactions`
- `GET  /api/v1/forum/games/{gameId}/search`

## Database

MongoDB `forum`

## Events

- **Out:** forum.post_stats_changed
- **In:** game.published

See [docs/contracts.md](../../docs/contracts.md) for payloads.

## TODO checklist

- [ ] Domain models and invariants
- [ ] HTTP adapters matching contracts
- [ ] Persistence (migrations or Mongo indexes)
- [ ] Outbox publish / inbox consume as listed above
- [ ] Tests for happy path + money/auth edge cases if applicable
- [ ] Extend `scripts/demo.sh` section for this service's US IDs
- [ ] Keep `/api/v1/forum/health` and `/health` green

## Local run

Service starts via `docker compose up forum forum-worker`.  
OpenAPI: `http://localhost:<port>/docs` (see HANDOFF for ports).
