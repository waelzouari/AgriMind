# Testing strategy

## Principles

Tests run without Raspberry Pi hardware by default. Hardware tests are a
separate, opt-in suite. No test result is recorded as passing until it has run
in the named environment. Safety, authorization, idempotency, and offline
recovery receive the same attention as happy paths.

## Test pyramid

### Edge

- Unit: soil conversion/calibration bounds, ultrasonic calculations, payload
  schemas, command validation, state transitions, duration caps, mode policy,
  feedback classification, weather freshness, schedule evaluation, outbox
  deduplication, and clock edge cases.
- Application boundary: deterministic fake sensors, adapter protocol
  compatibility, partial failure, unavailable/invalid readings, stale
  last-known values, recovery, UTC timestamps, and secret-safe structured logs.
- Pump safety boundary: explicit transitions, bounded automatic stop, manual
  and idempotent OFF, duplicate replay, command-ID conflicts, wrong targets,
  expiry/future timing, overlapping ON commands, timer isolation, actuator and
  scheduler failures, safe retry, fault state, shutdown, and structured logs.
- MQTT boundary: snapshot mapping, v1 serialization/topics, QoS/retention,
  verified TLS setup, LWT-before-connect ordering, ONLINE/OFFLINE status,
  unavailable broker behavior, disconnect/reconnect recovery, partial publish
  failure, exact command subscription restoration, broker-neutral inbound
  delivery, correlated ACK lifecycle, malformed and duplicate commands,
  exact-identity ACL policy, credential redaction, and no pump/GPIO dependency
  using deterministic fakes rather than Internet access.
- Contract: JSON Schema examples and compatibility for MQTT envelopes.
- Persistence: idempotent migrations, atomic event/outbox insertion, ordered
  restart recovery, PUBACK-gated delivery, 24-hour retention, failure fallback,
  and command idempotence across restart using temporary SQLite and fake MQTT.
- Failover: Cloud-first selection, threshold/delay/cooldown behavior, a single
  active command subscription, passive Cloud recovery, local PUBACK isolation,
  Cloud outbox drain, cross-broker idempotency, and secret-safe configuration.
- Integration: fake hardware plus local Mosquitto; duplicate QoS 1 delivery;
  retained-command protection; disconnect/reconnect; SQLite restart recovery;
  ingestion acknowledgement.
- Hardware: each sensor, active-low relay boot/cleanup, emergency stop, maximum
  runtime, sensor disconnect, and a supervised soak test.

### Backend / Supabase

- Migration/reset validation in disposable PostgreSQL databases and the local
  Supabase stack when its CLI is installed.
- Constraints, indexes, timestamps, idempotency keys, and invalid enum/range
  inputs.
- RLS matrix with at least user A, user B, anonymous, and privileged ingestion
  roles across SELECT/INSERT/UPDATE/DELETE.
- Private Storage bucket policies and signed URL expiry.
- Ingestion replay and duplicate-event tests.
- Trusted telemetry/status ingestion: topic/payload/registry identity checks,
  inactive and unknown devices, timestamp windows, atomic duplicate/conflict
  classification, manual MQTT acknowledgment, and transient persistence retry.
- Offline-to-Cloud synchronization: broker acceptance versus Cloud
  confirmation, stable message identity, receipt validation, permanent
  rejection, restart/redelivery convergence, and the 24-hour boundary.
- Weather: deterministic rolling-window and clock-boundary tests, fake HTTP
  adapter tests with no Internet, persistent cache behavior, location-change
  invalidation, and PostgreSQL integration tests for coordinate constraints,
  grants, RLS, service writes, and cross-farm isolation. A live Open-Meteo
  smoke test is optional and never required by ordinary CI.

### Flutter

AGM-017 tests the telemetry topic builder and strict v1 decoder, wrong-identity
filtering, all four metrics, duplicate/out-of-order suppression, stale data,
connection/reconnection events, missing-data UI, and session disposal through
fakes. Ordinary CI never connects to HiveMQ or requires physical hardware.

- Unit: authentication session restoration, auth-state observation, safe
  provider-error mapping, repeated-submit suppression, one-farm lookup and
  creation recovery, repositories, validators, command construction, reconnect
  state, and state controllers.
- Widget: startup restoration without login flash, login validation and safe
  errors, logout, protected-route gating, farm-check loading, onboarding form,
  lookup/create failure and retry, loading/empty/error/offline states, sensor
  cards, stale-data indicator, pump confirmation and pending/rejected
  acknowledgement.
- Integration: session restore, minimal farm onboarding, live dashboard, manual
  irrigation, mode switch, and weather fallback.
- Accessibility: contrast, text scaling, touch target sizes, semantics, and
  outdoor-readable status independent of color alone.

### AI / data

- Dataset schema, provenance manifest, licences, duplicates, missingness, class
  balance, unit consistency, and leakage checks before training.
- Deterministic preprocessing and seeded splits; prefer group/time split when
  repeated measurements would leak across random rows.
- Logistic-regression or rule baseline before more complex models.
- Report precision, recall, F1, PR-AUC/ROC-AUC as appropriate, confusion matrix,
  calibration, and latency on Raspberry Pi. Never invent thresholds or scores.
- Version feature schema, preprocessing pipeline, model artifact, dataset
  fingerprint, code commit, and evaluation report together.
- CV adds subject/source-aware splits, domain-shift tests using demo-plant
  photos, low-confidence behavior, image validation, and latency.

## Failure and safety matrix

Required scenarios include broker loss, Internet loss, Supabase loss, stale
weather, malformed payloads, duplicated/out-of-order commands, reboot while
pump runs, clock drift, full disk, SQLite corruption recovery, sensor timeout,
ML load/inference failure, local/cloud broker transition, and reconnection sync.

The expected safe result is explicit for every scenario; in no case may a cloud
failure or inference exception leave the pump energized indefinitely.

## CI progression

1. Foundation: secret scan, Python formatting/lint/type checks/tests, Markdown
   links, and JSON Schema validation.
2. Mobile: Dart format, analyze, unit/widget tests.
3. Backend: local Supabase migrations and RLS tests.
4. Integration: containerized Mosquitto and ingestion tests.
5. AI: lightweight preprocessing/reproducibility tests; training is a separate
   reproducible workflow, not a required job on every commit.

Hardware suites and live cloud tests remain manual or scheduled with protected
credentials; they do not block ordinary pull requests unless a release gate
requires them.

## Release evidence

Each ticket links acceptance criteria to automated test names and any manual
evidence. The TecWeek release additionally requires a 24-hour offline buffer
test, command latency measurements, physical fail-safe verification, credential
rotation checklist, clean-device setup rehearsal, and the complete 3-5 minute
demo plus Plan B rehearsal.
