# ADR-008: Irrigation feedback persistence

- Status: Accepted
- Date: 2026-09-24
- Ticket: AGM-025

## Context

AGM-005 emits observable command acknowledgements (`accepted`, `rejected`,
`completed`, and `failed`). The existing V1 `IrrigationResult` instead records
a measured before/after soil-moisture verification. These facts have different
meanings and must not be conflated. AGM-008 provides one transactional SQLite
event store/outbox, AGM-013 distinguishes MQTT PUBACK from Cloud persistence,
and AGM-012 provides the trusted device registry and Supabase boundary.

## Decision

Persist each existing `CommandAcknowledgement` as the technical irrigation
lifecycle, using its stable `acknowledgement_id`. `accepted` is not
`completed`; `completed` proves only the technical stop observed by AGM-005 and
does not prove water volume, improved moisture, or agronomic success.

Keep `IrrigationResult` V1 unchanged and accept it only when real valid before
and after measurements already exist. AGM-025 introduces no infiltration delay,
timer, inferred measurement, or automatic conversion from an acknowledgement.

Both event types use the existing AGM-008 SQLite database and outbox. Event and
outbox insertion remain atomic. Exact redelivery is idempotent; reuse of an ID
with different immutable content is a conflict. QoS 1 delivery is at-least-once.
A PUBACK means broker acceptance only; a correlated application receipt from
the trusted ingestion service moves the row to `cloud_confirmed` or `rejected`.

The Cloud worker validates the V1 topic and schema, QoS/retain rules, freshness,
active registered device, and authoritative farm association before calling
service-role-only idempotent RPCs. Flutter and anonymous/authenticated clients
retain read-only RLS access and never receive privileged credentials.

Persistence observes AGM-005 output and cannot authorize actuation. SQLite
failure retains the existing best-effort MQTT fallback and secret-safe audit
loss logging; it does not silently redefine AGM-005 or AGM-024 safety policy.

## Consequences

- Manual, Scheduled, and AI requests can share one lifecycle observer at the
  AGM-005 acknowledgement source, including asynchronous completion/failure.
- Offline rows replay with stable identities after reconnect and converge by
  database deduplication.
- No agronomic result is produced when a reliable after measurement is absent.
- No online learning, relabeling, model update, threshold update, or retraining
  occurs in AGM-025.
- The 24-hour Edge retention policy still bounds local audit history.
