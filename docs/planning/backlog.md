# Dependency-aware backlog

## Milestones

| Milestone | Exit condition |
|---|---|
| M0 - Architecture & Foundations | Repository, contracts, CI, safety design, and ownership decisions approved |
| M1 - Edge-to-MQTT Vertical Slice | Real sensor telemetry and safe remote pump command work through cloud MQTT, with fake-hardware CI |
| M2 - P0 Mobile & Cloud | Auth, minimal farm setup, Supabase isolation, live dashboard, manual control, and weather work end-to-end |
| M3 - P0 Intelligent Irrigation | Defensible model/policy, automatic mode, feedback loop, offline buffer, and failure tests pass |
| M4 - P1 Farm & Vision | Scheduling, tree grid, visual inspection, notifications, and history are integrated after P0 stability |
| M5 - Demo Release | Security review, soak/failure tests, runbook, Plan B, and release rehearsal pass |

## Labels

Priority: `priority:P0`, `priority:P1`, `priority:P2`.

Type: `type:architecture`, `type:feature`, `type:bug`, `type:infra`,
`type:test`, `type:docs`.

Area: `area:edge`, `area:mqtt`, `area:backend`, `area:mobile`, `area:ai`,
`area:security`, `area:weather`, `area:demo`.

Workflow: `status:blocked`, `needs:hardware`, `needs:decision`.

## Ordered backlog

| ID | Title | Pri | Milestone | Depends on |
|---|---|---:|---|---|
| AGM-001 | Repository foundation and architecture | P0 | M0 | - |
| AGM-002 | Capture wire contracts and configuration model | P0 | M0 | AGM-001 |
| AGM-003 | Integrate and characterize existing hardware drivers | P0 | M0 | AGM-001 |
| AGM-004 | Edge ports, fake hardware, and sensor service | P0 | M1 | AGM-002, AGM-003 |
| AGM-005 | Safe pump state machine and local command handler | P0 | M1 | AGM-003, AGM-004 |
| AGM-006 | Cloud MQTT connection, telemetry, LWT, and ACL design | P0 | M1 | AGM-002, AGM-004 |
| AGM-007 | MQTT command acknowledgements and idempotent remote control | P0 | M1 | AGM-005, AGM-006 |
| AGM-008 | SQLite event store, outbox, and 24-hour buffer | P0 | M1 | AGM-004 |
| AGM-009 | Local Mosquitto fallback and explicit failover runbook | P0 | M1 | AGM-006, AGM-007, AGM-008 |
| AGM-010 | Supabase schema migrations and constraints | P0 | M2 | AGM-001, AGM-002 |
| AGM-011 | Supabase Auth, RLS, Storage, and isolation tests | P0 | M2 | AGM-010 |
| AGM-012 | Device registry and secure telemetry ingestion service | P0 | M2 | AGM-006, AGM-010, AGM-011 |
| AGM-013 | Offline-to-cloud synchronization and deduplication | P0 | M3 | AGM-008, AGM-012 |
| AGM-014 | Flutter foundation and AgriMind design system | P0 | M2 | AGM-001 |
| AGM-015 | Authentication and session restoration | P0 | M2 | AGM-011, AGM-014 |
| AGM-016 | Minimal one-farm onboarding and configuration | P0 | M2 | AGM-010, AGM-015 |
| AGM-017 | Mobile MQTT session and realtime sensor dashboard | P0 | M2 | AGM-006, AGM-014, AGM-015, AGM-016 |
| AGM-018 | Manual irrigation mobile flow with acknowledgement UX | P0 | M2 | AGM-007, AGM-017 |
| AGM-019 | Open-Meteo adapter, aggregation, caching, and freshness policy | P0 | M2 | AGM-016 |
| AGM-020 | Weather UI and stale/offline states | P0 | M2 | AGM-014, AGM-019 |
| AGM-021 | Irrigation dataset audit and versioned feature contract | P0 | M3 | AGM-002, AGM-019 |
| AGM-022 | Irrigation baseline, split methodology, and evaluation | P0 | M3 | AGM-021 |
| AGM-023 | Versioned local irrigation inference adapter | P0 | M3 | AGM-004, AGM-022 |
| AGM-024 | AI automatic mode with independent edge safety gate | P0 | M3 | AGM-005, AGM-019, AGM-023 |
| AGM-025 | Irrigation feedback loop and result persistence | P0 | M3 | AGM-008, AGM-012, AGM-024 |
| AGM-026 | P0 end-to-end, offline, and failure scenario suite | P0 | M3 | AGM-009, AGM-013, AGM-018, AGM-020, AGM-025 |
| AGM-027 | Local scheduled irrigation | P1 | M4 | AGM-005, AGM-008, AGM-016 |
| AGM-028 | Digital Farm Manager schema refinement and repositories | P1 | M4 | AGM-010, AGM-011 |
| AGM-029 | Farm grid and tree detail UI | P1 | M4 | AGM-014, AGM-028 |
| AGM-030 | CV dataset audit and reproducible training pipeline | P1 | M4 | AGM-001 |
| AGM-031 | CV model evaluation and secured inference API | P1 | M4 | AGM-030 |
| AGM-032 | Smartphone visual inspection and private image storage | P1 | M4 | AGM-011, AGM-029, AGM-031 |
| AGM-033 | Event notifications and push delivery | P1 | M4 | AGM-011, AGM-012, AGM-025, AGM-032 |
| AGM-034 | Complete sensor, irrigation, and inspection history | P1 | M4 | AGM-012, AGM-025, AGM-032 |
| AGM-035 | Security review, secret scanning, and threat test pass | P0 | M5 | AGM-026 |
| AGM-036 | Demo hardening, observability, runbook, and rehearsal | P0 | M5 | AGM-026, AGM-035; selected P1 only if complete |
| AGM-037 | TecWeek release preparation | P0 | M5 | AGM-036 |

`AGM-027` is definitively P1. Manual and AI automatic irrigation are P0. The
explicit MVP priority table controls implementation sequencing, so scheduled
irrigation does not block AGM-026 or the P0 vertical slice.

## First-ticket acceptance criteria

### AGM-001 - Repository foundation and architecture

**Objective:** establish a reproducible monorepo skeleton and approved system
boundaries without implementing product features.

Acceptance criteria:

- Directory structure reflects the approved system architecture.
- Python, Flutter, Supabase, contracts, deployment, docs, and CI ownership are
  explicit; generated/secret/data files are ignored.
- Root README includes prerequisites and setup entry points.
- `.env.example` contains names and safe descriptions only.
- Architecture diagram, scope decisions, and top risks are reviewed by all
  three members.
- ADR-001 records the monorepo/boundary decision.
- Minimal Python package and test discovery work on a non-Raspberry Pi machine.
- CI runs formatting/lint/test placeholders without requiring GPIO or secrets.
- No prototype driver behavior is modified and no credential is committed.

Testing: clean clone/bootstrap smoke test, Python test discovery, secret scan,
and CI configuration validation.

Definition of Done: criteria pass, documentation is current, diff is
self-reviewed, CI is green, and a PR targets `develop`.

### AGM-002 - Capture wire contracts and configuration model

Acceptance criteria:

- Versioned JSON Schemas exist for telemetry, commands, acknowledgements,
  device status, and irrigation results.
- Topic construction is centralized and uses lowercase versioned paths.
- Command schema includes UUID, farm/device, issue/expiry times, and bounded
  duration; invalid examples fail tests.
- Environment configuration validates at startup and redacts secrets in logs.
- `.env.example` documents cloud and local broker modes without credentials.

### AGM-003 - Integrate and characterize existing hardware drivers

Acceptance criteria:

- Original driver files are copied with provenance and behavior preserved.
- Accepted GPIO/calibration map is documented and configurable.
- Imports do not initialize hardware unexpectedly.
- Driver-level tests use module fakes; supervised hardware checklist verifies
  GPIO and active-low relay behavior.
- Pump is forced OFF on initialization, cleanup, SIGTERM, and handled failure.
- Tank measurements are not a critical interlock until physical calibration is
  signed off.

### AGM-004 - Edge ports, fake hardware, and sensor service

Acceptance criteria:

- Sensor and actuator protocols have real and fake implementations.
- Domain/application tests import on macOS/Linux without Pi-only packages.
- Sensor snapshots preserve per-reading quality/error information and UTC time.
- Partial sensor failure does not discard healthy readings.
- Structured logs contain correlation IDs and no secrets.

### AGM-005 - Safe pump state machine and local command handler

Acceptance criteria:

- State machine, allowed transitions, duration cap, cooldown, and watchdog are
  tested with a fake clock and fake relay.
- Duplicate/stale/invalid commands never re-actuate the pump.
- Automatic and scheduled requests pass agronomic decision and system safety as
  separate checks; manual requests still obey hard safety constraints.
- Boot, exception, stop signal, timeout, and fault force relay OFF.
- Every acceptance/rejection/state transition produces an auditable event.

## Branch and pull-request strategy

- Create `develop` from the initial approved foundation; protect `main` and
  `develop` once their first commits exist.
- Work on `feature/AGM-XXX-short-description`, `fix/AGM-XXX-description`, or
  `docs/AGM-XXX-description` from current `develop`.
- One primary ticket per PR, targeting `develop`; related tiny enabling changes
  are linked explicitly rather than silently expanding scope.
- Require passing CI, issue link, test evidence, no-secret check, and one teammate
  review. Safety/security changes require the relevant domain owner.
- Release through a reviewed `develop -> main` PR tagged `v0.x.y`; emergency
  fixes branch from `main` and are merged back into `develop`.

## Implementation order and team parallelism

After AGM-001/002 establish contracts, the three-person team can work in three
lanes: edge (AGM-003-009), cloud/mobile (AGM-010-020), and AI/weather
(AGM-019, AGM-021-023). Integration gates are AGM-007 (physical vertical
slice), AGM-018 (user-controlled vertical slice), AGM-025 (closed feedback
loop), and AGM-026 (P0 reliability). P1 work starts only after AGM-026 passes.

## Proposed start

- First ticket: AGM-001.
- First branch after approval: `feature/AGM-001-project-foundation`, based on
  `develop`.
- Exact next action: review the contradictions/decisions in the discovery report
  and approve AGM-001; then create the branches and implement only that ticket.
