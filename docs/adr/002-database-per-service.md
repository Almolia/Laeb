# ADR-02: Database-per-service (logical)

## Status
Accepted

## Decision
One Postgres container with one database + one user per relational service.
One Mongo container with one database per document service.
No shared schemas, no cross-database joins.

## Consequences
Satisfies the database-per-service pattern with lower RAM. Scaling to separate instances is a Compose change, not a code change.
