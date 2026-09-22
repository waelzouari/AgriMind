# Initial discovery report

Status: analysis complete; implementation requires approval.

## Sources inspected

- The complete 60-page `AgriMind MVP - Cahier des Charges Technique et
  Fonctionnel - TecWeek 3.0` (version 1.0, September 2026), including tables,
  diagrams, test matrices, roadmap, and references.
- The supplied Raspberry Pi files: `dht22.py`, `soil.py`, `ultrasonic.py`,
  `pump.py`, and `app.py`.
- Supporting prototype files required to understand them: `config.py`,
  `main.py`, `requirements.txt`, the prototype README, and the four original
  hardware test scripts.
- The current AgriMind repository and Git/GitHub state.

The current repository contains only `.git`; the prototype remains in the
Downloads directory and has not been copied or modified.

## Requirements summary

AgriMind must deliver a French-language, competition-ready MVP organized around
`DETECT -> UNDERSTAND -> ALERT -> ACT -> VERIFY`:

1. An edge service on Raspberry Pi 4 reads soil moisture, air temperature and
   humidity, and tank level; it safely controls one active-low pump relay.
2. MQTT transports telemetry, commands, acknowledgements, device status, and
   irrigation results. Cloud transport uses TLS and authentication; commands
   use QoS 1 or better, strict validation, farm isolation, and idempotency.
3. Supabase provides authentication, PostgreSQL persistence, Storage, RLS, and
   optional server functions. Privileged keys never enter the mobile app.
4. Flutter provides authentication, a live P0 dashboard, weather, device state,
   manual control, and AI automatic irrigation. P1 adds scheduling, farm/tree
   management, visual inspection, richer history, and notifications.
5. Open-Meteo supplies farm-local current weather, rain aggregates at 6/12/24
   hours, prior 24-hour rain, and ET0 behind a cacheable service abstraction.
6. Irrigation ML predicts only `irrigation_needed: 0|1` from agronomic inputs.
   Tank, pump, and sensor status remain independent safety inputs.
7. Every actuation is decided finally at the edge and followed by an auditable
   before/after soil-moisture verification workflow.
8. The Raspberry Pi remains autonomous for at least 24 hours without Internet,
   buffering telemetry and executing cached schedules locally.
9. Computer vision is binary visual anomaly classification, not diagnosis. The
   smartphone is the MVP image source; the rover is explicitly future scope.

## Existing prototype assessment

| Area | Verified behavior | Decision |
|---|---|---|
| DHT22 | `board.D17`, `use_pulseio=False`; 3 retries; 2-second retry delay; device reset on terminal error | Preserve driver and wrap with an adapter |
| Soil | ADS1115 A0; 10 samples at 50 ms; `DRY=28000`, `WET=11000`; clamped linear percentage | Preserve conversion; make calibration configurable and test it |
| Ultrasonic | BCM 23/24; 10 us trigger; 1-second echo timeouts; tank height 30 cm and offset 2 cm in current config | Preserve pins; add median filtering and treat as non-critical monitoring |
| Pump | BCM 18; active-low: LOW=ON, HIGH=OFF; initialization and cleanup force OFF | Preserve exactly; add duration cap, interlocks, watchdog, and command idempotency above it |
| Scheduler | Five-second loop; in-memory latest/history; threshold auto mode with hysteresis | Retain as reference, not as final domain model |
| Flask app | Local demo UI, WebSocket telemetry, hard-coded users/secret, permissive CORS, direct pump calls | Keep only as a legacy diagnostic tool; do not expose it as production control |

The working code is the authority for wiring. Therefore the accepted GPIO map
is DHT22 17, relay 18 active-low, HC-SR04 trigger 23/echo 24, ADS1115 A0. The
PDF's provisional DHT22 4 and relay 17 values are rejected pending a physical
wiring test.

## Scope map

| Existing | P0 - first reliable vertical slice | P1 - after P0 | Future / excluded |
|---|---|---|---|
| RPi 4 and wired sensors; relay/pump; local Flask demo; calibrated soil conversion; local threshold logic | Driver integration; fake hardware; safe actuation; SQLite outbox; MQTT cloud telemetry/control; local broker fallback; Supabase/Auth/RLS foundation; Flutter auth/dashboard/manual/AI modes; Open-Meteo; validated irrigation baseline; feedback loop; core failure tests | Local scheduled irrigation; farm grid and trees; CV dataset/model/API; camera flow; push notifications; complete history; settings | Autonomous rover; disease diagnosis; multi-farm user experience; multiple irrigation zones; precise litres/session; advanced analytics |

## Contradictions and decisions

1. **Relay polarity:** PDF HW-06/HW-07 says HIGH starts and LOW stops the pump,
   contradicting the proven active-low driver. The tested driver wins; the PDF
   test cases must be corrected before execution.
2. **GPIO values:** PDF values marked "to confirm" conflict with working code.
   The working map above is the baseline, followed by a physical pin audit.
3. **Tank dimensions:** the PDF describes a roughly 7.7 cm demo reservoir while
   current config uses 30 cm plus a 2 cm offset. This remains a hardware
   calibration task; tank level cannot be a hard interlock until verified.
4. **Scheduled mode priority (resolved):** manual and AI automatic irrigation
   are P0; scheduled irrigation is P1. The explicit MVP priority table governs
   implementation sequencing, so scheduling remains in the MVP vision but
   cannot block the P0 end-to-end vertical slice.
5. **Farm creation priority:** the mobile priority list defers Farm Manager, but
   FR-02 and weather/ML require farm coordinates and crop/soil context. P0 uses
   a minimal one-farm onboarding/configuration flow; the grid/tree UI remains P1.
6. **Notifications:** the scope table lists push notifications as P1, while the
   notification matrix calls several P0. P0 records events and shows in-app
   status; push delivery is P1 unless declared a competition requirement.
7. **Offline manual control:** the matrix claims remote control is unavailable
   without Internet, yet FR-20 accepts local MQTT control. The design supports
   optional same-LAN control through the local broker, but never pretends a
   remote phone can reach the Pi without a network path.
8. **MQTT to Supabase path:** MQTT does not persist into Supabase by itself. A
   cloud ingestion service is required and must authenticate the device and
   deduplicate events.
9. **Service-role key on edge:** the PDF suggests edge devices may use a
   Supabase service-role key. This is rejected. A device-scoped ingestion API or
   broker-to-backend service owns privileged access.
10. **Direct Flutter MQTT credentials:** embedding shared broker credentials is
    unsafe. For the MVP, provision per-user/per-device scoped credentials or a
    short-lived credential endpoint; authorization remains enforced at both
    broker ACLs and edge validation.
11. **ML data joins:** the proposed public datasets do not share compatible
    rows for all desired features. They must not be naively concatenated or have
    synthetic weather attached without provenance. A reduced-feature baseline
    is acceptable until a defensible dataset exists.
12. **Weather fallback:** "model can work with reduced features" is only valid
    if such a model is separately trained and versioned. Otherwise use
    freshness-bounded cached weather or a conservative rules fallback.
13. **Single farm vs topic future-proofing:** database and topics retain
    `farm_id`, but the P0 UI enforces one farm per user.
14. **Growth stage:** required by the ML feature list but absent from the farm
    schema/onboarding. Add a controlled nullable field or exclude it from the
    first model contract.
15. **Irrigation-to-tree history:** irrigation events are farm-wide in the
    proposed schema, yet tree details claim zone irrigation history. Add a
    nullable `zone_id` to events for P1 and do not infer tree-specific watering
    from farm-wide events.

## Missing decisions / information

- TecWeek deadline, available person-days, team skill distribution, and target
  mobile devices.
- Physical confirmation of the soil sensor model, relay module polarity, tank
  height/offset, power isolation, and whether a flyback/protection circuit is
  present.
- Selected MQTT broker and its ACL/credential capabilities.
- Supabase project environments and region; CV/ingestion hosting target.
- Maximum safe pump runtime, cooldown, flow failure behavior, and emergency-stop
  procedure.
- Definitive automatic irrigation duration policy and agronomic thresholds.
- Dataset licences, actual schemas, class balance, provenance, and permission to
  redistribute artifacts.
- Weather cache maximum age and conservative behavior after it expires.
- Whether same-LAN mobile control is required during Internet loss.
- Whether push notifications are a hard demo gate. Scheduled mode is resolved
  as P1 and is not a P0 release gate.

These unknowns do not block architecture work. They become explicit ticket
acceptance gates before the relevant behavior is enabled on hardware.

## Principal risks

- Physical harm or water damage from duplicate, stale, or malformed commands.
- A boot/restart leaving the active-low relay energized.
- Weak MQTT authorization causing cross-farm command injection.
- Loss or duplication during offline synchronization.
- Misleading ML caused by label leakage, incompatible datasets, or unmeasured
  metrics.
- DHT22/HC-SR04 instability and invalid calibrations presented as trustworthy.
- Demo dependence on Internet, cloud APIs, or credentials.
- A three-person team spreading effort across P1 before the vertical slice is
  reliable.

## Decision gate

The proposed first delivery ticket is AGM-001. The proposed first working branch
is `feature/AGM-001-project-foundation`, created from `develop` after the team
approves this plan. The exact next action is to approve or amend the decisions
above, then create `develop` and that feature branch and implement only AGM-001.
