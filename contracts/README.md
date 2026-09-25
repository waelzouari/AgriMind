# Shared contracts

Versioned MQTT and service-boundary JSON Schemas live under their wire version,
starting with `v1/`. Contracts are transport definitions, not a place for
business logic. Backward compatibility and validation tests accompany every
schema change.

The schemas use JSON Schema Draft 2020-12 and are language-neutral so Flutter,
backend services, and edge code can implement the same messages. Python models
in `edge/src/agrimind_edge/contracts/` provide strict runtime validation and
canonical JSON serialization for the edge process.

`ingestion-acknowledgement.schema.json` correlates only telemetry persistence
results. It is distinct from pump-command acknowledgements and never contains
the original telemetry payload or credentials.

`cv-inference-response.schema.json` and `cv-inference-error.schema.json` define
the authenticated, farm-scoped AGM-031 HTTP result boundary. The only visual
classes are `NORMAL` and `ANOMALY`; the reported anomaly softmax probability is
not calibrated confidence, a diagnosis, treatment advice, or irrigation input.
