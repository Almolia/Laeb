# ADR-03: Drop Elasticsearch

## Status
Accepted

## Decision
Use Postgres full-text for store search and MongoDB text indexes for forum search.
Do not run Elasticsearch in Phase 2.

## Consequences
Saves ~1 GB RAM. Phase 1 report §3.2 / §5.2 should note this deviation.
