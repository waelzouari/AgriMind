# ADR-007: AI automatic irrigation with an independent local safety gate

- Status: Accepted
- Date: 2026-09-24

## Context

AGM-023 produces an advisory local irrigation recommendation from three fresh
sensor measurements. A recommendation is not permission to energize a physical
pump. Manual MQTT commands and AGM-027 schedules already converge on the
AGM-005 command handler and safe pump state machine.

AGM-019 weather is an informative Cloud capability and has no Edge runtime
boundary. The HC-SR04 reservoir readings are monitoring-only until physical
calibration is complete. Neither source can safely become an implicit physical
interlock in AGM-024.

## Decision

Add a distinct, opt-in AI automatic path:

```text
SensorSnapshot -> AGM-023 inference -> independent local safety gate
               -> AGM-005 PumpCommandHandler -> SafePumpController -> PumpPort
```

The independent gate verifies successful compatible inference, the three local
sensor qualities and timestamps, current pump state, and an AI-only in-memory
cooldown. Only an explicit `ALLOW` permits the orchestrator to submit a bounded
canonical pump command to AGM-005. AGM-005 remains the actuation authority and
rechecks identity, duration, concurrency, state transitions, and automatic
stop behavior.

Automatic mode defaults to disabled. When enabled, duration and cooldown must
both be configured explicitly. Cooldown begins only after AGM-005 returns an
`accepted` acknowledgement. AGM-024 exposes one `evaluate_once()` cycle and
does not introduce a timer, background worker, or autonomous cadence.

Weather remains outside the physical actuation path, missing weather is never
treated as zero rainfall, and Cloud data cannot authorize the pump. Reservoir
level remains monitoring-only and no water-level threshold is invented.

## Consequences

- ML/model failure, invalid or stale local inputs, safety failure, disabled
  mode, pump conflict, or active cooldown all fail closed.
- Manual, scheduled, and AI requests share one existing command/state-machine
  authority; AGM-024 adds no second physical controller.
- The AI cooldown is intentionally lost on process restart. Persisted automatic
  outcomes and feedback belong to AGM-025.
- Physical Raspberry Pi behavior still requires a separate supervised test.

## Alternatives considered

- Direct actuation from inference was rejected because it would make an ML
  recommendation a physical authorization.
- Reusing Cloud weather as an Edge interlock was rejected because it would add
  an unavailable network dependency and contradict AGM-019's boundary.
- Reservoir thresholds were rejected until the HC-SR04 installation is
  physically calibrated.
- A periodic AI loop was deferred because no approved cadence or restart policy
  exists; AGM-024 provides only one explicit cycle.
