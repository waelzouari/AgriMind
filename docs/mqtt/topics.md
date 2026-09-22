# MQTT contract

## Naming

All topics are lowercase ASCII:

```text
agrimind/v1/farms/{farm_id}/devices/{device_id}/telemetry/{metric}
agrimind/v1/farms/{farm_id}/devices/{device_id}/commands/{command}
agrimind/v1/farms/{farm_id}/devices/{device_id}/acks/{command_id}
agrimind/v1/farms/{farm_id}/devices/{device_id}/status/{kind}
agrimind/v1/farms/{farm_id}/devices/{device_id}/events/{event_type}
```

The normalized lowercase prefix resolves the PDF's mixed `AgriMind` examples.
Adding protocol version and device identity permits schema evolution and avoids
ambiguity if multiple devices are introduced later.

## Initial topics

| Topic suffix | Direction | QoS | Retained |
|---|---|---:|---:|
| `telemetry/soil_moisture` | edge -> broker | 1 | no |
| `telemetry/temperature` | edge -> broker | 1 | no |
| `telemetry/humidity` | edge -> broker | 1 | no |
| `telemetry/tank_level` | edge -> broker | 1 | no |
| `commands/pump` | client -> edge | 1 | no |
| `commands/mode` | client -> edge | 1 | no |
| `commands/schedule` | client -> edge | 1 | no |
| `acks/{command_id}` | edge -> client | 1 | no |
| `status/pump` | edge -> broker | 1 | yes |
| `status/device` | edge -> broker | 1 | yes; LWT writes offline |
| `events/irrigation_result` | edge -> broker | 1 | no |

Never retain actuator commands.

## Envelope

Telemetry:

```json
{
  "schema_version": 1,
  "message_id": "uuid",
  "device_id": "uuid",
  "farm_id": "uuid",
  "recorded_at": "2026-09-22T08:00:00Z",
  "value": 65.2,
  "unit": "%",
  "quality": "valid"
}
```

Pump command:

```json
{
  "schema_version": 1,
  "command_id": "uuid",
  "farm_id": "uuid",
  "device_id": "uuid",
  "action": "on",
  "duration_seconds": 30,
  "issued_at": "2026-09-22T08:00:00Z",
  "expires_at": "2026-09-22T08:00:30Z",
  "requested_by": "uuid"
}
```

The edge rejects unknown fields where the schema marks them closed, invalid
IDs, mismatched farm/device, expired commands, unsupported actions, out-of-range
duration, unsafe state, and duplicate commands. Acknowledgements contain
`accepted|rejected|completed`, a stable reason code, and the observed pump state.

## Connection behavior

- Cloud: MQTT over TLS on 8883 with certificate and hostname verification.
- Commands and acknowledgements: QoS 1 minimum.
- Unique client IDs; clean-start/session settings selected explicitly.
- Exponential backoff with jitter and a configured upper bound.
- LWT publishes retained `online=false`; successful connection publishes a
  retained online heartbeat with firmware version and timestamp.
- Broker ACLs are the first farm-isolation layer; edge validation is the second.
- Local fallback is explicit and observable. It must not silently downgrade a
  cloud TLS connection to an unauthenticated LAN broker.
