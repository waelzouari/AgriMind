# ADR-005: Cloud ingestion acknowledgements

- Status: accepted
- Date: 2026-09-23
- Ticket: AGM-013

## Context

AGM-008 marked an outbox row delivered after the edge received a QoS 1
PUBACK. That proves broker acceptance, not that AGM-012 committed the event to
Supabase. The edge could therefore stop retrying before Cloud persistence.

## Decision

AGM-012 publishes a minimal v1 telemetry-ingestion acknowledgement after a
terminal result. `persisted` and `duplicate` confirm durable Cloud convergence;
`rejected` records a correlatable permanent failure. Transient failures emit no
receipt. The edge keeps broker-accepted telemetry replayable until a receipt is
validated and stored.

Receipts use QoS 1, are not retained, contain no telemetry or diagnostic text,
and are validated against their topic plus the locally provisioned farm/device
identity. Rejected events remain locally auditable until the normal 24-hour
purge. Existing AGM-008 `delivered` rows migrate conservatively to
`broker_accepted`.

## Consequences

The system remains at-least-once. A crash can republish telemetry or receipts;
stable `message_id` values and PostgreSQL idempotency make exact duplicates
converge safely. No claim of exactly-once or zero data loss is made. Device
status, command acknowledgements, irrigation results, GPIO, and pump safety are
outside this decision.
