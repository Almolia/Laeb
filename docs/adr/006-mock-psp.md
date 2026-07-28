# ADR-06: Payment gateway is mocked

## Status
Accepted

## Decision
`mock-psp` container accepts charge requests and callbacks a webhook.
We never receive, log, or store card numbers (NFR-04).

## Consequences
Wallet top-up demo works without a real bank; PCI scope stays out of our services.
