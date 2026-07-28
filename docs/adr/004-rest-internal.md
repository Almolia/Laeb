# ADR-04: REST + JSON internally (not gRPC)

## Status
Accepted

## Decision
Order → Catalog and Order → Wallet use HTTP/JSON. Sync call boundaries unchanged from Phase 1; only transport differs.

## Consequences
Less tooling overhead across 11 services. Optional Day-3 stretch: gRPC for Wallet.debit only.
