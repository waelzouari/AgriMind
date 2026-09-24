# P0 end-to-end validation matrix

AGM-026 assembles the existing P0 boundaries into deterministic journeys. It
does not add a runtime feature. The automated suite uses the packaged portable
irrigation model, application services, SQLite, canonical MQTT contracts, the
trusted ingestion service, and fake transports/hardware. It performs no network
access and never imports GPIO.

## Automated journeys

| Journey | Automated evidence | Expected result |
| --- | --- | --- |
| AI automatic happy path | `test_ai_happy_path_reaches_cloud_confirmation_without_physical_hardware` | A real AGM-023 recommendation passes the independent AGM-024 gate, reaches the AGM-005 handler and `FakePump`, creates a correlated `accepted` ACK, becomes broker-accepted in the SQLite outbox, is persisted by trusted ingestion, and becomes Cloud-confirmed only after the application receipt. |
| AI stale-input failure | `test_stale_ai_snapshot_is_blocked_before_pump_or_lifecycle` | Stale sensor input fails closed before command submission; no pump call, ACK, MQTT publication, or outbox entry is created. |
| Manual MQTT command | `test_manual_mqtt_command_reaches_fake_pump_and_durable_correlated_ack` | A canonical non-retained QoS 1 pump command crosses the AGM-007 processor and AGM-005 safety boundary; `FakePump` starts and the correlated QoS 1 ACK is durable. |
| Offline recovery | `test_offline_ack_replay_preserves_identity_and_requires_cloud_receipt` | A disconnected publication stays pending, replay preserves its ID and payload, PUBACK changes only broker state, duplicate Cloud ingestion is idempotent, and the application receipt alone establishes Cloud confirmation. |

These tests complement, rather than duplicate, `test_mqtt_failover.py`: AGM-009
already owns Cloud/local broker selection, thresholds, cooldown, subscription
ownership, and cross-broker command idempotency.

## P0 safety and failure matrix

| Condition | Authority/evidence | Safe invariant |
| --- | --- | --- |
| ML unavailable, invalid, incompatible, or throws | AGM-023 and AGM-024 tests | Unknown is never converted to permission; the pump is not called. |
| Sensor missing, invalid, stale, or future-dated | AGM-023/024 tests plus AGM-026 stale journey | Automatic irrigation fails closed locally. |
| Negative ML recommendation | AGM-024 tests | A recommendation of “no irrigation” cannot reach the pump boundary. |
| Independent gate blocks or fails | AGM-024 tests | Recommendation is not actuation permission. No external or ML path bypasses the local gate. |
| Pump busy, faulted, wrong target, expired command, excessive duration | AGM-005/007/024/027 tests | The existing state machine rejects the request; no overlapping actuation is created. |
| Duplicate or conflicting command | AGM-005/007/008/009 tests | Stable identity is replayed idempotently; conflicting content fails safely. |
| Broker or Internet unavailable | AGM-008/009 plus AGM-026 offline journey | Durable outbound events remain pending and replay with the same identity. Incoming commands are never stored for later actuation. |
| MQTT PUBACK received but Cloud persistence absent | AGM-013 plus AGM-026 offline journey | Broker acceptance is not Cloud persistence; the event remains pending. |
| Duplicate Cloud delivery | AGM-012/013 plus AGM-026 offline journey | Persistence is idempotent and emits a correlated duplicate receipt. |
| Supabase/trusted persistence unavailable | AGM-012/013 tests | The event remains retryable; failure cannot authorize the pump. |
| Weather unavailable or stale | Existing AGM-019/020 tests | Weather remains informational in P0 automatic actuation; missing weather is never interpreted as zero rain. |
| Cloud/local broker failover | `test_mqtt_failover.py` | One active command source, passive recovery, and local physical authority are preserved. |
| SQLite unavailable/corrupt/full | AGM-008 persistence tests | Best-effort publication is explicit; commands are not replayed from the outbox and safety remains local. |
| Process restart during command/schedule lifecycle | AGM-005/008/027 tests | The pump controller owns safe shutdown; claimed schedules recover as unknown rather than being actuated twice. |

## Boundary semantics

- A command ACK is a technical lifecycle event (`accepted`, `rejected`,
  `completed`, or `failed`). It does not prove an agronomic outcome.
- An `IrrigationResult` is a separately observed AGM-025 feedback event. The P0
  runtime does not invent a moisture delta or an infiltration delay.
- MQTT QoS 1 and PUBACK provide at-least-once broker delivery, not database
  persistence. A canonical ingestion acknowledgement closes the Cloud loop.
- Edge SQLite never stores inbound MQTT commands in the outbox and never
  replays a command into the pump.
- Weather, Flutter, Supabase, MQTT, and ML cannot bypass the Raspberry Pi local
  safety gate and the AGM-005 state machine.

## Environment coverage and limitations

Ordinary CI uses fake sensors, `FakePump`, fake MQTT, temporary SQLite, and the
real contract/application code. It does not require a Raspberry Pi, GPIO,
HiveMQ, Mosquitto, Supabase Cloud, or Open-Meteo. The existing Flutter weather
tests cover fresh/stale/offline presentation without live network access.

Physical relay behavior, a real Raspberry Pi reboot while energized, real
broker latency, and the release 24-hour soak remain supervised release evidence;
they are not implied by this automated suite.
