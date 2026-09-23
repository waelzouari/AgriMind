# ADR-004: Device ingestion authentication and service-role isolation

- Status: Accepted
- Date: 2026-09-23
- Ticket: AGM-012

## Context

Edge devices publish QoS 1 telemetry and retained status through HiveMQ Cloud.
Flutter cannot write event tables under AGM-011 RLS, and privileged Supabase
credentials are forbidden on the edge. MQTT 3.1.1 subscribers do not receive a
portable authenticated-publisher identity with each message.

## Decision

HiveMQ authenticates each device using an individual username/password and
enforces exact per-device publish ACLs. The trusted ingestion subscriber uses a
separate read-only broker principal. It validates the v1 topic and payload, but
derives authoritative farm ownership and activation from `public.devices`.

Only the independently deployed ingestion service holds the Supabase
`service_role`. Atomic RPCs recheck the device while locked, insert by durable
message ID, distinguish exact duplicates from identity conflicts, and update
`last_seen_at` only for new accepted events. RPC execution is revoked from
`public`, `anon`, and `authenticated`; AGM-011 RLS remains unchanged.

Device MQTT passwords remain broker-managed and are not stored in PostgreSQL.
Cloud data cannot actuate hardware; all pump commands still pass through the
Raspberry Pi command handler and safety gate.

## Consequences

- Topic and payload farm IDs are untrusted assertions until checked against the
  registry.
- Deployment security depends on correctly provisioned and tested broker ACLs.
- Revocation coordinates registry deactivation and broker credential removal.
- A stable persistent MQTT session and manual acknowledgment support retry, but
  no end-to-end HiveMQ durability claim is made before supervised validation.
- Client certificates and application-layer signatures are deliberately not
  introduced in AGM-012.
