# Shared contracts

Versioned MQTT and service-boundary JSON Schemas live under their wire version,
starting with `v1/`. Contracts are transport definitions, not a place for
business logic. Backward compatibility and validation tests accompany every
schema change.

The schemas use JSON Schema Draft 2020-12 and are language-neutral so Flutter,
backend services, and edge code can implement the same messages. Python models
in `edge/src/agrimind_edge/contracts/` provide strict runtime validation and
canonical JSON serialization for the edge process.
