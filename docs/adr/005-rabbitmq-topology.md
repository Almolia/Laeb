# ADR-05: RabbitMQ topology

## Status
Accepted

## Decision
One topic exchange `platform.events`. Routing key = event name. One durable queue per consumer (`q.<service>`).
Transactional Outbox in producers; `processed_events` inbox for idempotent consumers.

## Consequences
Reliable async workflows (NFR-06) without distributed transactions.
