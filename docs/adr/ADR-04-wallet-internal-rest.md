# ADR-04: REST for synchronous Wallet integration

- Status: Accepted
- Date: 2026-07-28

## Context

The Phase 1 report describes synchronous Order-to-Wallet calls as gRPC. The Phase 2 plan
standardises the implementation on Python/FastAPI and REST/JSON so every service shares one
transport, error envelope, authentication middleware, and OpenAPI contract.

## Decision

Wallet exposes synchronous internal operations as versioned REST endpoints under
`/api/v1/wallet/internal`. Asynchronous trade settlement continues to use RabbitMQ. This changes
only the transport; Wallet remains an independently deployed bounded context with its own
PostgreSQL database.

All money-moving internal requests require `Idempotency-Key`, propagate `X-Correlation-Id`, and
return the common error envelope. Order and Trading integrate only through these contracts and
events; they never read Wallet tables.

## Consequences

- Phase 1 documentation must name REST rather than gRPC for Wallet calls.
- The service contract is directly executable through OpenAPI and curl.
- A future gRPC adapter can be added without changing domain or application logic.
