# Runtime configuration

`RuntimeConfig.from_environment()` fails before transport startup when identity,
broker, TLS, interval, version, secret, or existing hardware configuration is
invalid. It composes the unchanged `HardwareConfig` from AGM-002.

## Non-secret configuration

| Variable | Rule |
|---|---|
| `AGRIMIND_FARM_ID` | required canonical non-zero UUID |
| `AGRIMIND_DEVICE_ID` | required canonical non-zero UUID |
| `AGRIMIND_MQTT_HOST` | required hostname/IPv4 literal without URL scheme/path |
| `AGRIMIND_MQTT_PORT` | integer 1-65535; default 8883 |
| `AGRIMIND_MQTT_TLS_ENABLED` | `true` or `false`; default true |
| `AGRIMIND_MQTT_CA_FILE` | required absolute path when TLS is enabled |
| `AGRIMIND_TELEMETRY_INTERVAL_SECONDS` | integer 1-3600; default 5 |
| `AGRIMIND_CONTRACT_VERSION` | exactly `v1` |
| `AGRIMIND_PUMP_MAX_DURATION_SECONDS` | local limit 1-600; default 600; commands above it are rejected |
| `AGRIMIND_GPIO_*`, ADS1115/calibration/tank values | validated by `HardwareConfig` |

## Secrets

`AGRIMIND_MQTT_USERNAME` and `AGRIMIND_MQTT_PASSWORD` are required at runtime
and stored only in `MqttCredentials`. Its fields are excluded from generated
dataclass representations, and its explicit `repr` displays `***`. The parent
runtime representation uses only that redacted representation.

Real secrets belong in an ignored `.env` with restrictive permissions or the
deployment environment/secret store. They must not appear in `.env.example`,
payloads, topics, logs, exceptions, fixtures, screenshots, issues, or commits.
Supabase privileged credentials remain forbidden on Flutter and Raspberry Pi.

The placeholders in `.env.example` are deliberately non-operational. Replace
them only in an ignored local/runtime environment.
