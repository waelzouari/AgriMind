# MQTT v1 wire contract

Status: implemented by AGM-003 as transport-independent contracts. MQTT
connections, publish/subscribe behavior, broker ACLs, QoS handling, retained
messages, and LWT configuration belong to later tickets.

## Common rules

- Wire version: `v1` in topics and `schema_version: 1` in payloads.
- Encoding: UTF-8 JSON object; deterministic Python output uses sorted keys and
  compact separators. Consumers must not depend on JSON key order.
- Identifiers: lowercase, hyphenated, non-zero UUID strings.
- Time: RFC 3339 UTC ending in `Z`; producers emit millisecond precision.
- Unknown fields, unsupported versions/enums, malformed IDs/timestamps, and
  nonfinite numbers are rejected.
- Payloads never contain credentials. Arrival through MQTT is transport, not
  authorization and never bypasses Raspberry Pi safety checks.
- Language-neutral JSON Schemas are in `contracts/v1/`; edge runtime models are
  in `agrimind_edge.contracts`.

## Canonical topics

All topic strings are constructed by `TopicBuilder`, not concatenated at call
sites. They are lowercase ASCII:

```text
agrimind/v1/farms/{farm_id}/devices/{device_id}/telemetry/{metric}
agrimind/v1/farms/{farm_id}/devices/{device_id}/commands/pump
agrimind/v1/farms/{farm_id}/devices/{device_id}/acks/{command_id}
agrimind/v1/farms/{farm_id}/devices/{device_id}/status/device
agrimind/v1/farms/{farm_id}/devices/{device_id}/events/irrigation_result
```

Topic farm/device IDs must equal the corresponding payload fields. That
cross-check belongs to future MQTT handlers, not the message model alone.

| Topic suffix | Direction | Purpose | Future QoS/retained |
|---|---|---|---|
| `telemetry/{metric}` | edge -> broker | One sensor measurement | QoS 1 / no |
| `commands/pump` | trusted client -> edge | Request bounded ON or OFF | QoS 1 / never retained |
| `acks/{command_id}` | edge -> client | Correlated command outcome | QoS 1 / no |
| `status/device` | edge -> broker | Heartbeat/last device state | QoS 1 / retained |
| `events/irrigation_result` | edge -> broker | VERIFY feedback result | QoS 1 / no |

## Telemetry

Schema: `contracts/v1/telemetry.schema.json`.

Example on `.../telemetry/soil_moisture`:

```json
{
  "schema_version": 1,
  "message_id": "33333333-3333-4333-8333-333333333333",
  "farm_id": "11111111-1111-4111-8111-111111111111",
  "device_id": "22222222-2222-4222-8222-222222222222",
  "metric": "soil_moisture",
  "value": 65.2,
  "unit": "%",
  "recorded_at": "2026-09-22T08:00:00.000Z",
  "quality": "valid"
}
```

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `schema_version` | integer | yes | exactly `1` |
| `message_id` | string | yes | canonical non-zero UUID; deduplication identity |
| `farm_id` | string | yes | canonical non-zero UUID |
| `device_id` | string | yes | canonical non-zero UUID |
| `metric` | string enum | yes | `soil_moisture`, `temperature`, `humidity`, `tank_level` |
| `value` | number | yes | finite JSON number; no NaN/infinity |
| `unit` | string enum | yes | soil/humidity `%`; temperature `°C`; tank level `cm` |
| `recorded_at` | string | yes | UTC RFC 3339 timestamp |
| `quality` | string enum | yes | `valid` or `estimated` |

Telemetry contains a raw measurement only. Agronomic recommendations, pump
state, and tank-based safety decisions do not belong in this message.

## Pump command

Schema: `contracts/v1/pump-command.schema.json`.

Example on `.../commands/pump`:

```json
{
  "schema_version": 1,
  "command_id": "44444444-4444-4444-8444-444444444444",
  "farm_id": "11111111-1111-4111-8111-111111111111",
  "device_id": "22222222-2222-4222-8222-222222222222",
  "action": "on",
  "duration_seconds": 30,
  "issued_at": "2026-09-22T08:00:00.000Z",
  "expires_at": "2026-09-22T08:00:30.000Z",
  "requested_by": "55555555-5555-4555-8555-555555555555"
}
```

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `schema_version` | integer | yes | exactly `1` |
| `command_id` | string | yes | canonical non-zero UUID; idempotency key |
| `farm_id` | string | yes | canonical non-zero UUID |
| `device_id` | string | yes | canonical non-zero UUID |
| `action` | string enum | yes | `on` or `off`; no implicit toggle |
| `duration_seconds` | integer | for `on` only | 1 through 600 inclusive; forbidden for `off` |
| `issued_at` | string | yes | UTC RFC 3339 timestamp |
| `expires_at` | string | yes | UTC, strictly after issue time and future at receipt |
| `requested_by` | string | yes | canonical non-zero user/service UUID for audit only |

`requested_by` is not proof of authorization. Deserialization rejects expired
commands, but future handlers must also match topic/payload identity,
deduplicate `command_id`, authenticate the sender, apply local safety rules,
and acknowledge the outcome. This contract does not perform GPIO actuation.

## Command acknowledgement

Schema: `contracts/v1/command-acknowledgement.schema.json`.

Example rejection on `.../acks/44444444-4444-4444-8444-444444444444`:

```json
{
  "schema_version": 1,
  "acknowledgement_id": "33333333-3333-4333-8333-333333333333",
  "command_id": "44444444-4444-4444-8444-444444444444",
  "farm_id": "11111111-1111-4111-8111-111111111111",
  "device_id": "22222222-2222-4222-8222-222222222222",
  "status": "rejected",
  "occurred_at": "2026-09-22T08:00:01.000Z",
  "reason_code": "safety_interlock",
  "pump_state": false
}
```

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `schema_version` | integer | yes | exactly `1` |
| `acknowledgement_id` | string | yes | canonical non-zero UUID |
| `command_id` | string | yes | original command UUID; must match topic suffix |
| `farm_id`, `device_id` | string | yes | canonical non-zero UUIDs |
| `status` | string enum | yes | `accepted`, `rejected`, `completed`, `failed` |
| `occurred_at` | string | yes | UTC RFC 3339 timestamp |
| `reason_code` | string | rejected/failed only | lowercase snake_case, max 64 |
| `pump_state` | boolean | no | observed logical pump state when available |

Reason codes are stable codes, not free-form secret-bearing diagnostics.
`accepted` means the edge accepted the request; `completed` means the requested
action completed. A published command is neither.

## Device status

Schema: `contracts/v1/device-status.schema.json`.

Example on `.../status/device`:

```json
{
  "schema_version": 1,
  "message_id": "33333333-3333-4333-8333-333333333333",
  "farm_id": "11111111-1111-4111-8111-111111111111",
  "device_id": "22222222-2222-4222-8222-222222222222",
  "online": true,
  "pump_state": false,
  "health": "healthy",
  "recorded_at": "2026-09-22T08:00:00.000Z",
  "uptime_seconds": 3600,
  "firmware_version": "0.1.0",
  "errors": []
}
```

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `schema_version` | integer | yes | exactly `1` |
| `message_id`, `farm_id`, `device_id` | string | yes | canonical non-zero UUIDs |
| `online` | boolean | yes | connection/heartbeat representation |
| `pump_state` | boolean | yes | last known logical pump state |
| `health` | string enum | yes | `healthy`, `degraded`, `fault` |
| `recorded_at` | string | yes | UTC RFC 3339 timestamp |
| `uptime_seconds` | integer | yes | zero or greater |
| `firmware_version` | string | yes | 1-64 characters |
| `errors` | string array | yes | up to 16 lowercase snake_case codes, max 64 each |

Later MQTT work may use the same shape for heartbeat and LWT-derived offline
state. AGM-003 does not configure LWT or publish status.

## Irrigation result

Schema: `contracts/v1/irrigation-result.schema.json`.

Example on `.../events/irrigation_result`:

```json
{
  "schema_version": 1,
  "event_id": "33333333-3333-4333-8333-333333333333",
  "farm_id": "11111111-1111-4111-8111-111111111111",
  "device_id": "22222222-2222-4222-8222-222222222222",
  "soil_moisture_before": 42.1,
  "soil_moisture_after": 68.3,
  "delta": 26.2,
  "result": "increased",
  "completed_at": "2026-09-22T08:20:00.000Z"
}
```

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `schema_version` | integer | yes | exactly `1` |
| `event_id`, `farm_id`, `device_id` | string | yes | canonical non-zero UUIDs |
| `soil_moisture_before` | number | yes | finite percentage from 0 through 100 |
| `soil_moisture_after` | number | yes | finite percentage from 0 through 100 |
| `delta` | number | yes | `after - before`, rounded to one decimal |
| `result` | string enum | yes | positive `increased`, zero `unchanged`, negative `decreased` |
| `completed_at` | string | yes | UTC RFC 3339 timestamp after verification |

This represents VERIFY output only. AGM-003 does not start the pump, wait for
infiltration, classify sensor noise, or persist the event.

## Evolution rules

- Consumers reject unsupported `schema_version` and topic version.
- V1 producers do not add undocumented fields because v1 schemas are closed.
- A backward-incompatible semantic change requires a future versioned topic and
  schema; no speculative v2 exists.
- Additive v1 evolution requires coordinated schema, Python, Dart, docs, and
  compatibility-test updates before deployment.
