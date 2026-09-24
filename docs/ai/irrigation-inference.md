# AGM-023 local irrigation inference

AGM-023 turns the reviewed AGM-022 baseline into a versioned, offline advisory
edge boundary. It does not add automatic irrigation or pump control.

## Runtime flow

```text
SensorSnapshot
  -> validate V1 quality, units, values, UTC time and freshness
  -> ordered Feature Contract V1 vector
  -> integrity-checked portable decision tree
  -> score and AGM-022 threshold
  -> advisory IrrigationRecommendation
```

The exact feature order is:

1. `soil_moisture_index_0_100`
2. `air_temperature_c`
3. `air_relative_humidity_percent`

Tank state, raw ADC, weather and identifiers are not features. The decision
threshold remains `0.02040816326530612`. The score is a train-leaf class
frequency, not a calibrated agronomic probability.

## Input policy

All three measurements must be finite, in their contractual ranges, have the
expected `percent`/`celsius` units, and carry `ReadingQuality.VALID` with UTC
observation times. `ReadingQuality.STALE` is rejected even if its age is below
the configured limit. The oldest feature observation determines snapshot age.
Future observations and ages greater than
`AGRIMIND_IRRIGATION_INFERENCE_MAX_AGE_SECONDS` are rejected; the MVP default is
30 seconds and is independent of Flutter telemetry display policy.

## Failure semantics

A successful result has a finite score and a Boolean recommendation. Missing,
invalid, stale, future, incompatible, corrupt or unavailable inputs/models
produce `score = None` and `irrigation_recommended = None`, with stable status
and reason codes. Failure is never converted into a negative recommendation.

The service has no `PumpPort`, MQTT transport, command handler, duration, or
GPIO dependency. Any future consumer must still pass an independent local
safety gate before actuation.

## Artifact and integrity

The edge wheel includes `baseline-v1.json` and its deterministic SHA-256
sidecar. The adapter verifies both before strict parsing and loads the model
only once. Joblib is never loaded by the edge.

Regenerate the portable artifact only from the trusted local AGM-022 Joblib:

```bash
agrimind-irrigation-export-tree \
  --joblib ai/irrigation/artifacts/baseline-v1.joblib \
  --evaluation ai/irrigation/evaluation/baseline-v1.json \
  --output edge/src/agrimind_edge/adapters/ml/models/baseline-v1.json \
  --digest-output edge/src/agrimind_edge/adapters/ml/models/baseline-v1.sha256 \
  --overwrite
```

The source Joblib and raw dataset remain ignored. Ordinary CI verifies the
portable runtime without either file. When the trusted local Joblib is present,
the optional parity test also proves that regeneration produces the exact
tracked JSON and digest.

## Evidence boundary

Automated tests demonstrate deterministic software behavior, strict artifact
compatibility and source-estimator parity. They do not establish agronomic
validity, Raspberry Pi latency or memory usage, nor physical pump behavior.
