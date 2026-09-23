# ADR-002: Broker selection and local fallback

Status: accepted for AGM-009.

HiveMQ Cloud is primary. Authenticated Mosquitto is an explicitly enabled local
fallback. The deterministic states are `OFFLINE`, `CLOUD_ACTIVE`,
`FAILOVER_PENDING`, `LOCAL_FALLBACK`, and `CLOUD_RECOVERY`. Failure thresholds,
delays, minimum residence, probe cadence, and recovery stability are runtime
configuration rather than hidden business constants.

Only the active broker owns the exact QoS 1 pump-command subscription. Cloud
may reconnect as a passive probe during local fallback, but receives no command
subscription until local is disconnected. Both brokers feed the same command
processor, persistent idempotency register, handler, controller, and pump port.

The SQLite outbox remains Cloud-authoritative. Local publications are mirrors:
a local PUBACK never marks a Cloud outbox row delivered. Consequently Cloud
recovery drains all non-expired pending events and retains at-least-once
semantics.

Local authentication and per-device ACLs are mandatory. TLS may be omitted
only on loopback or an explicitly isolated demo LAN; it is required on shared
or untrusted networks. Cloud verified TLS is unchanged and mandatory.
