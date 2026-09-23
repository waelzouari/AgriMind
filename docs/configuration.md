# Runtime configuration

`RuntimeConfig.from_environment()` fails before transport startup when identity,
broker, TLS, interval, version, secret, or existing hardware configuration is
invalid. It composes the unchanged `HardwareConfig` from AGM-002.

## Non-secret configuration

### Flutter client

The mobile build receives `AGRIMIND_SUPABASE_URL` and
`AGRIMIND_SUPABASE_ANON_KEY` through Flutter `--dart-define` values. Both are
public client configuration; the latter may be the Supabase anonymous or newer
publishable key. They must be paired with AGM-011 RLS. Flutter must never
receive `service_role`, a database password, a JWT signing secret, or device
credentials. Local `.env` files are not bundled or loaded by the mobile app.

### Edge device

| Variable | Rule |
|---|---|
| `AGRIMIND_FARM_ID` | required canonical non-zero UUID |
| `AGRIMIND_DEVICE_ID` | required canonical non-zero UUID |
| `AGRIMIND_MQTT_HOST` | required hostname/IPv4 literal without URL scheme/path |
| `AGRIMIND_MQTT_PORT` | integer 1-65535; default 8883 |
| `AGRIMIND_MQTT_TLS_ENABLED` | `true` or `false`; default true |
| `AGRIMIND_MQTT_CA_FILE` | required absolute path when TLS is enabled |
| `AGRIMIND_TELEMETRY_INTERVAL_SECONDS` | integer 1-3600; default 5 |
| `AGRIMIND_MQTT_KEEPALIVE_SECONDS` | integer 10-3600; default 60 |
| `AGRIMIND_MQTT_RECONNECT_MIN_SECONDS` | integer 1-3600; default 1 |
| `AGRIMIND_MQTT_RECONNECT_MAX_SECONDS` | integer from reconnect minimum through 3600; default 60 |
| `AGRIMIND_CONTRACT_VERSION` | exactly `v1` |
| `AGRIMIND_PUMP_MAX_DURATION_SECONDS` | local limit 1-600; default 600; commands above it are rejected |
| `AGRIMIND_SQLITE_PATH` | absolute local database path; default `/var/lib/agrimind/edge.sqlite3` |
| `AGRIMIND_MQTT_FAILOVER_ENABLED` | explicit `true`/`false`; default false |
| `AGRIMIND_LOCAL_MQTT_HOST`, `AGRIMIND_LOCAL_MQTT_PORT` | authenticated local broker endpoint |
| `AGRIMIND_LOCAL_MQTT_TLS_ENABLED`, `AGRIMIND_LOCAL_MQTT_CA_FILE` | optional local TLS; CA required when enabled |
| `AGRIMIND_MQTT_CLOUD_FAILURE_THRESHOLD` | consecutive failures before fallback eligibility; default 3 |
| `AGRIMIND_MQTT_FAILOVER_DELAY_SECONDS` | minimum failure duration; default 30 |
| `AGRIMIND_MQTT_LOCAL_MIN_ACTIVE_SECONDS` | minimum local residence; default 60 |
| `AGRIMIND_MQTT_CLOUD_PROBE_INTERVAL_SECONDS` | Cloud recovery observation cadence; default 30 |
| `AGRIMIND_MQTT_CLOUD_STABILITY_SECONDS` | required stable Cloud interval; default 30 |
| `AGRIMIND_GPIO_*`, ADS1115/calibration/tank values | validated by `HardwareConfig` |

## Secrets

`AGRIMIND_MQTT_USERNAME` and `AGRIMIND_MQTT_PASSWORD` are required at runtime
and stored only in `MqttCredentials`. Its fields are excluded from generated
dataclass representations, and its explicit `repr` displays `***`. The parent
runtime representation uses only that redacted representation.
When fallback is enabled, separate `AGRIMIND_LOCAL_MQTT_USERNAME` and
`AGRIMIND_LOCAL_MQTT_PASSWORD` values are required and receive the same
redaction. Cloud credentials must not be reused for the local broker.

Real secrets belong in an ignored `.env` with restrictive permissions or the
deployment environment/secret store. They must not appear in `.env.example`,
payloads, topics, logs, exceptions, fixtures, screenshots, issues, or commits.
Supabase privileged credentials remain forbidden on Flutter and Raspberry Pi.

The placeholders in `.env.example` are deliberately non-operational. Replace
them only in an ignored local/runtime environment.

The cloud adapter refuses to start when TLS is disabled or no CA path is
present, even though `tls=false` remains available to separately scoped local
test/demo adapters. Reconnect settings configure bounded exponential backoff;
they are not application retry loops.

## Trusted ingestion server

AGM-012 has a separate server-only configuration surface under
`backend/services/ingestion/.env.example`:

| Variable | Classification |
|---|---|
| `AGRIMIND_INGESTION_MQTT_HOST`, `..._PORT` | server configuration |
| `AGRIMIND_INGESTION_MQTT_CLIENT_ID` | stable non-secret session identity |
| `AGRIMIND_INGESTION_MQTT_CA_FILE` | trusted CA path |
| `AGRIMIND_INGESTION_MQTT_USERNAME`, `..._PASSWORD` | server-only broker secret |
| `AGRIMIND_INGESTION_SUPABASE_URL` | server configuration |
| `AGRIMIND_INGESTION_SUPABASE_SERVICE_ROLE_KEY` | privileged server-only secret |
| `AGRIMIND_INGESTION_MAXIMUM_AGE_SECONDS` | defaults to 86400 (24 hours) |
| `AGRIMIND_INGESTION_MAXIMUM_FUTURE_SKEW_SECONDS` | defaults to 300 (5 minutes) |

These values belong in the ingestion deployment secret store or an ignored
server-local environment file. The service-role variable must never be copied
to the repository-root edge/mobile environment, Flutter, or Raspberry Pi.
