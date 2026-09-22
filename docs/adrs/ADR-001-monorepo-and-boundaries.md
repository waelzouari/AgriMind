# ADR-001: Monorepo and system boundaries

- Status: Accepted
- Date: 2026-09-22
- Decision owners: AgriMind team
- Ticket: AGM-001

## Context

Three developers must deliver and demonstrate an edge, cloud, mobile, and AI
system while preserving hardware safety and offline behavior. Separate
repositories would add coordination overhead and make contract changes harder
to review atomically.

## Decision

Use one monorepo with top-level ownership boundaries for edge, mobile, backend,
AI, shared wire contracts, deployment, documentation, and scripts.

The Raspberry Pi is the final physical safety authority. Domain/application
code depends on ports; GPIO, MQTT, persistence, weather, and inference are
adapters. Supabase privileged credentials remain in server-side services and
never enter Flutter or the Raspberry Pi. P0 is completed before P1 starts.

## Consequences

- Cross-component contracts and documentation can change in one reviewed PR.
- CI can select checks by directory while retaining an end-to-end view.
- CODEOWNERS may be added later when team ownership is known.
- The repository can grow large if raw datasets or model artifacts are checked
  in, so those outputs are ignored and require an explicit artifact policy.
- Boundaries require discipline; proximity in one repository does not permit
  direct imports across independently deployed components.

## Alternatives considered

- **Repository per component:** stronger physical separation but excessive
  coordination and versioning overhead for a three-person competition team.
- **Single undifferentiated application:** initially faster but unsafe and hard
  to test because domain logic would couple to GPIO, cloud, and UI concerns.
