# Edge hardware architecture

## AGM-002 scope

This layer integrates the validated NexusGuard hardware drivers only. It does
not contain MQTT, irrigation decision logic, schedules, cloud persistence, or
user-interface behavior. Broader edge services belong to later tickets.

## Authoritative physical mapping

| Component | Verified configuration | Prototype behavior |
|---|---|---|
| DHT22 | BCM GPIO 17 | `use_pulseio=False`; temperature and relative humidity |
| Pump relay | BCM GPIO 18 | Active-low: LOW is ON, HIGH is OFF |
| HC-SR04 | Trigger BCM 23, echo BCM 24 | 10 us trigger pulse; 1-second echo timeouts |
| Soil sensor | ADS1115 channel A0 over I2C | Ten readings averaged; 50 ms between reads |

The specification's DHT22 GPIO 4 and relay GPIO 17 were explicitly marked
indicative/to-confirm. They are not used because the working physical prototype
and its source code verify GPIO 17 and 18 respectively.

## Driver boundaries and provenance

The adapters in `edge/src/agrimind_edge/adapters/hardware/` derive from the
NexusGuard files supplied for AGM-002:

- `sensors/dht22.py`: lazy device creation, three reads by default, two-second
  spacing after transient `RuntimeError`, one-decimal results, and cleanup on a
  terminal error.
- `sensors/soil.py`: lazy ADS1115 A0 channel, ten-sample integer average, 50 ms
  sampling delay, `DRY=28000` / `WET=11000` linear conversion, and 0-100 clamp.
- `sensors/ultrasonic.py`: BCM setup, 200 us settle, 10 us trigger, one-second
  rising/falling echo timeouts, `distance * 17150`, and the existing tank-level
  formula.
- `actuators/pump.py`: lazy BCM setup, active-low output, logical state, and
  best-effort safe cleanup.

Behavior is preserved while module globals are replaced by adapter instances
and injected minimal protocols. These are intentional testability changes, not
changes to sensor formulas or GPIO semantics. The only new input guards reject
invalid retry/sample counts and invalid physical configuration before hardware
access. One intentional safety improvement supplies `initial=HIGH` while GPIO
18 is configured as an output, preventing an active-low startup pulse before
the prototype's explicit HIGH/OFF write.

Raspberry Pi libraries are imported only when a `.raspberry_pi(config)` factory
is called. Importing the package on a developer or CI machine cannot initialize
GPIO, I2C, or a sensor.

## Pump safety

Constructing `PumpRelay` has no physical side effect. The owning runtime must
call `initialize()` during controlled startup; it configures BCM GPIO 18 as an
output and immediately writes HIGH/OFF. `turn_on()` also initializes safely
before writing LOW. `turn_off()` writes HIGH. `cleanup()` attempts HIGH before
releasing only GPIO 18 and always resets the logical state to OFF.

Automated tests use `FakeGPIO` and never import `RPi.GPIO` or energize a relay.
AGM-002 does not claim supervised physical verification; that remains an
explicit Raspberry Pi activity.

## Calibration and tank assumptions

The soil calibration values are inherited from the working prototype. They
must be re-measured for the actual probe and substrate before agronomic use.
The formula supports either calibration ordering but rejects equal endpoints.

Tank height 30 cm and sensor offset 2 cm are preserved from prototype config,
but conflict with the small reservoir dimensions described elsewhere in the
specification. Until physically calibrated, HC-SR04 output is monitoring-only
system state and is not a critical pump interlock or an ML feature.

## Raspberry Pi installation and smoke test

Use Raspberry Pi OS with I2C enabled. In a virtual environment:

```bash
python3 -m pip install -e "./edge[hardware]"
```

Create and validate `HardwareConfig` before constructing real adapters. Any
physical pump test must be supervised, begin with the water path secured, and
verify HIGH/OFF before allowing a LOW/ON command. No automated test suite may
instantiate the real pump factory.

## Legacy `app.py`

The inspected NexusGuard `app.py` is a Flask/Socket.IO local dashboard and
orchestration shell. It starts the legacy sensor loop, holds mutable global
state, changes thresholds at runtime, and calls the pump directly from REST and
WebSocket handlers. It also contains hard-coded demo users/session secret and
permissive CORS.

It is not copied into AgriMind and is not an architectural dependency. Flutter
will be the user-facing application. The useful hardware behavior was taken
from the dedicated driver modules; automatic decision logic from legacy
`main.py` is deliberately deferred to later tickets.

## Hardware-free tests

`pytest` supplies scripted DHT/ADC values, a scripted clock, and fake GPIO.
Coverage includes calibration bounds, averaging/timing, retry/error handling,
ultrasonic timing/timeout/calculation, active-low output, safe initialization
and cleanup, and configuration rejection. Run the complete foundation suite:

```bash
make check
```
