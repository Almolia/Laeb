# ADR-01: One language, one framework, one service template

## Status
Accepted

## Decision
Python 3.12 + FastAPI for all 11 services. Shared kernel in `libs/shared_kernel`.

## Consequences
One dependency list, shared Docker layers, one mental model for Wave B owners.
