# AgriMind MVP security review

## Review record and scope

This AGM-035 review covers repository state `5d9ed24` (AGM-026 merged) and the
security hardening added on top of it. It reviews the implemented P0 boundaries:
Flutter, Supabase Auth/RLS, MQTT, trusted ingestion, Edge, SQLite, Weather and the
local irrigation model. It does not assess unmerged AGM-030 work or claim a
penetration test of Supabase, HiveMQ, Android, Raspberry Pi or physical hardware.

The review validates existing controls and closes two bounded gaps: unbounded
inbound MQTT payload decoding and force-tracked sensitive repository paths. It
does not change authentication, RLS, MQTT topics, public JSON schemas or physical
safety policy.

## Trust boundaries and protected assets

| Boundary | Identity and authorization | Validation / failure behavior |
| --- | --- | --- |
| Flutter -> Supabase | Supabase session; RLS derives identity from `auth.uid()` | Anonymous, non-member and cross-farm access fail closed |
| Flutter -> HiveMQ | Separate telemetry, command and ACK identities; broker ACLs | Canonical device topics; Edge still revalidates every command |
| Edge -> HiveMQ | Device credential and verified TLS | Farm/device topic builder, durable outbox and safe offline behavior |
| HiveMQ -> ingestion | Trusted server MQTT identity | Topic, payload, QoS, retain, freshness and registry validation |
| Ingestion -> Supabase | Server-only `service_role` | Restricted `SECURITY DEFINER` RPCs and registered-device authority |
| Cloud/AI/schedule -> pump | Untrusted request or recommendation | Local handler, independent safety gate and safe state machine |
| Edge -> SQLite | Local service process and filesystem identity | Transactions, stable IDs, retention and idempotent replay |
| Weather -> Open-Meteo | Configured HTTPS provider | Timeouts, strict response validation and stale/unavailable states |
| Model artifact -> Edge | Versioned packaged JSON | Hash, metadata, tree structure, feature order and score validation |

Protected assets are pump authority, farm and device identity, Supabase sessions,
privileged credentials, farm-isolated data, telemetry, commands and ACKs,
irrigation history, the local event store, device registry and model integrity.

## Threat actors

The MVP threat model covers an unauthenticated Internet user, a farm A user
attempting farm B access, a compromised MQTT client, a spoofed or inactive device,
an unavailable or compromised Cloud component, a person with repository access,
operator configuration errors and a local Raspberry Pi user. Root or equivalent
physical compromise is not claimed to be contained by application controls.

## Authentication, authorization and isolation

Supabase owns token persistence and refresh. Flutter restores the session before
showing authenticated content, follows auth-state changes and clears authenticated
state on logout or session invalidation. Provider failures are mapped to safe user
messages without exposing tokens or exceptions.

RLS is enabled on all application tables. Membership helpers are minimal
`SECURITY DEFINER` functions with an empty `search_path`, schema-qualified objects
and restricted execution. Owners and members can read their farm data; only
owners receive the explicitly supported farm/tree mutations. Authenticated clients
cannot directly write memberships, devices or event tables. Anonymous access is
denied. Trusted ingestion RPCs are executable only by `service_role`.

Farm isolation is checked at each relevant boundary. RLS uses `auth.uid()` and
memberships. Mobile repositories reject mismatched rows. MQTT topic and payload
identities must agree. Ingestion resolves the device in the trusted registry and
rejects unknown, inactive or cross-farm devices. Database constraints bind event
farm/device pairs to the registered device.

## MQTT and device trust

Cloud MQTT uses verified TLS. Edge subscriptions are scoped to the canonical
device topics; the ingestion worker alone uses the broad server-side filters it
needs. Commands are QoS 1 and non-retained. Retained, malformed, expired,
future-issued, wrong-target, duplicate-conflicting and oversized commands fail
safely. Reconnect restores subscriptions without bypassing validation.

Inbound payloads are limited to **4,096 bytes before UTF-8 or JSON decoding** at
both untrusted application boundaries. The largest current canonical message is a
maximal device-status payload at 1,471 bytes (16 maximum-length error codes, a
maximum-length firmware version and a realistic 64-bit uptime). The limit provides
2.78 times that size and therefore ample room for every current canonical v1
producer while bounding decode work. A message above the limit is permanently
invalid: Edge does not correlate or actuate it; ingestion does not consult the
registry or persist it and can terminally broker-ACK it without publishing a false
persistence receipt.

The local Mosquitto fallback is loopback-only by default, disallows anonymous
clients and uses a password file plus exact ACL. If exposed to a LAN, it must use
TLS and an isolated trusted network. A local PUBACK is never treated as Cloud
persistence.

## Physical actuation, replay and offline behavior

Every implemented actuation path converges on the existing local boundary:

```text
manual MQTT / local schedule / AI recommendation
                       |
                       v
              PumpCommandHandler
                       |
                       v
              SafePumpController
                       |
                       v
                    PumpPort
```

AI recommendations additionally pass through the independent automatic safety
gate. No Cloud service, Flutter client, MQTT callback or model adapter directly
controls GPIO. Target, timing, duration, state, conflicts and idempotency are
checked before actuation. Initialization, failure recovery and shutdown attempt a
safe OFF; an unconfirmed safe state becomes FAULT rather than a false success.

Immutable IDs provide at-least-once convergence: identical duplicates replay the
same outcome, while the same ID with different content is rejected. Processed
commands survive restart and are never sourced from the outbound SQLite outbox.
Cloud/local duplicate delivery cannot actuate twice. Offline failover uses the same
processor and safety boundary and does not broaden permissions.

## Local SQLite posture

SQLite stores telemetry/events, outbound publications, command fingerprints,
results and schedules; it does not store Supabase or MQTT credentials. Deployment
must use a dedicated service account, a restrictive parent directory (normally
mode `0700`), and a database that is not world-readable. Configuration and secrets
must remain outside the database directory. Backups must preserve access controls,
be rotated with the retention policy and avoid copying live WAL state
inconsistently.

Transparent database encryption is not required for the MVP threat model. These
controls do not protect against root, the service account itself or an attacker
with equivalent local privileges.

## Secrets and Flutter

Real `.env` files, `.secrets/`, private keys/certificates, runtime databases,
password/ACL files, generated model artifacts and raw AI datasets are ignored and
also rejected if force-added to Git. Safe `.env.example` and ACL example files are
allowed. Secret scanning reports only filenames and candidate counts, never secret
values. Logs and configuration representations redact credentials.

Flutter is untrusted and contains only the public Supabase client configuration.
`service_role`, database passwords and other privileged credentials must never be
placed in Flutter, Edge or Git.

### SEC-035-01 — accepted MVP MQTT credential risk (MEDIUM)

A static Flutter MQTT command credential is extractable from an APK and therefore
cannot prove the identity of the human user. This is an accepted residual MVP risk.
Current mitigations are separate MQTT identities, narrow broker ACLs, farm/device
scope, canonical commands, expiry, idempotency, bounded duration and the local
physical safety boundary. A later production design should issue short-lived,
scoped broker identities or tokens. AGM-035 does not implement that redesign.

## Supabase and trusted ingestion

All privileged RPCs set a safe empty `search_path`, schema-qualify referenced
objects, revoke default/public execution and grant only the intended role. Initial
farm creation is an authenticated atomic operation; telemetry, status, command ACK
and irrigation-result ingestion are server-only operations.

Ingestion rejects invalid topics, duplicate JSON keys, invalid constants,
schema violations, topic/payload mismatch, wrong QoS/retain policy, stale/future
events and unregistered devices before trusted persistence. Transient persistence
failure causes retry; permanent invalid input is terminal. Raw payloads are not
logged.

## Weather and AI/model boundaries

Weather calls use HTTPS, timeouts, strict coordinates/timeline/value validation and
explicit fresh/stale/unavailable states. Missing weather is never interpreted as
zero rain and cannot authorize physical actuation.

The Edge runtime loads only the versioned portable JSON model. It verifies the
artifact digest, model/contract/methodology versions, dataset identity, ordered
features, target classes, decision threshold and bounded tree structure. Invalid,
stale or future sensor input and model failures yield no reliable recommendation.
Joblib is restricted to trusted local training/export and parity tests.

The invariant remains: **ML output is not physical permission**.

## Logging, resource bounds and supply chain

Security-relevant logs contain stable reason codes and validated identifiers, not
credentials or raw MQTT payloads. Client-facing errors do not expose server stack
traces.

Existing bounds cover pump duration, retry/backoff, HTTP timeouts, outbox batches
and retention, sensor/model freshness and model tree size. AGM-035 adds the missing
MQTT payload bound. Filesystem capacity remains an operational responsibility.

### Residual supply-chain risk (LOW)

GitHub Actions use mutable major-version references, the CI PostgreSQL image uses a
mutable major tag, Python dependency resolution is not fully hash-locked, and no
dedicated online vulnerability audit is configured. Existing linting, strict type
checking, tests and package builds reduce accidental risk. AGM-035 intentionally
does not update dependencies, add network scanners, pin Actions or change the CI
database image.

## Findings summary

| ID | Severity | Status |
| --- | --- | --- |
| SEC-035-01 | MEDIUM | Accepted MVP risk: extractable static mobile MQTT credential |
| SEC-035-02 | MEDIUM | Remediated: 4,096-byte pre-decode MQTT limit |
| SEC-035-03 | LOW | Remediated: tracked sensitive-path repository check |
| SEC-035-04 | LOW | Documented residual supply-chain risk |
| SEC-035-05 | LOW | Documented OS/filesystem dependency for SQLite |

## Security invariants

- Flutter is untrusted and never receives `service_role`.
- Farm A cannot access farm B through supported APIs.
- Unknown, inactive or cross-farm devices cannot ingest trusted data.
- Topic, payload and registered device identity must agree.
- Cloud and MQTT cannot bypass local physical safety.
- AI cannot bypass the independent safety gate.
- Duplicate or replayed commands cannot cause duplicate actuation.
- Expired, future, retained, malformed or oversized commands cannot actuate.
- Offline fallback cannot weaken authorization or safety.
- MQTT PUBACK is not proof of Cloud persistence.
- Privileged RPCs are unavailable to unauthorized roles.
- Physical pump duration remains locally bounded.
- Initialization, failure handling and cleanup preserve safe-OFF behavior.
- Secrets and runtime/generated sensitive files are not committed or logged.

## Release security checklist

- Run repository validation and secret scanning in the project environment.
- Confirm no `.env`, `.secrets/`, private key, runtime DB, Joblib or raw dataset is tracked.
- Run RLS/RPC tests from a clean local Supabase database.
- Run Edge, ingestion, Weather, AI and Flutter validation suites.
- Verify broker identities remain separate and ACLs are farm/device scoped.
- Verify Cloud TLS certificate validation remains enabled.
- Deploy Edge under a dedicated OS user with restrictive SQLite/config permissions.
- Confirm no service credential is present in the mobile build configuration.
- Record separately any real-broker or physical-hardware validation performed.

## Validation limitations

Automated tests use fakes and local services. This review does not claim a real
Raspberry Pi, GPIO, relay or physical pump security validation. It also does not
claim that CI validates live HiveMQ or Supabase Cloud configuration. Those systems
require separately supervised deployment checks.
