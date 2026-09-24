# ADR-006: Portable local irrigation model artifact

- Status: Accepted
- Date: 2026-09-24
- Decision owners: AgriMind team
- Ticket: AGM-023

## Context

AGM-022 selected a small scikit-learn decision tree and produced a local
Joblib file. Joblib is a Python object-serialization format: it is unsafe to
load from an untrusted source, opaque in review, dependent on Python/ML library
versions, and already produced different byte hashes across compatible local
environments. Installing the complete training stack on Raspberry Pi would
also couple edge inference to scikit-learn, NumPy, SciPy, and the raw dataset.

The edge must run deterministic inference offline while keeping model failures
separate from physical actuation. The three-feature V1 contract, AGM-022 model,
and selected threshold must remain unchanged.

## Decision

Export the trusted AGM-022 `DecisionTreeClassifier` automatically to the strict
`agrimind-decision-tree-v1` JSON format. Track the canonical JSON and a SHA-256
sidecar as packaged edge resources. The export includes the dataset,
methodology, model, feature-contract and artifact versions, exact ordered
features, target classes, decision threshold, and complete tree nodes.

The edge adapter uses only the Python standard library. It verifies the digest,
rejects duplicate/non-finite/unknown JSON values and fields, validates all
approved metadata and the full reachable acyclic tree, then caches the parsed
model. It never loads Joblib. An application port separates the model adapter
from snapshot validation and recommendation policy.

The trusted Joblib remains ignored and is used only as local training evidence,
as the export source, and for parity tests. Its hash is not a portable model
identity. The JSON is regenerated rather than manually transcribed, and parity
tests compare its scores with the source estimator.

Only `ReadingQuality.VALID` values may be inferred. `STALE` is always rejected;
the oldest of the three feature observations must be no more than the
configurable 30-second MVP maximum age. Future observations are rejected.
Failure yields no score and no recommendation.

## Consequences

- Raspberry Pi inference requires no ML framework, dataset, broker, or network.
- The runtime artifact is small, reviewable, deterministic, integrity-checked,
  and included in the edge wheel.
- A future model family requires a new explicitly supported portable format or
  a separate reviewed runtime decision; arbitrary estimators are not accepted.
- Scores remain dataset leaf frequencies, not calibrated agronomic
  probabilities.
- AGM-024 may consume a recommendation only through an independent safety
  boundary. AGM-023 cannot actuate the pump.

## Alternatives considered

- **Rebuild during deployment:** rejected because it requires the raw dataset
  and training dependencies on every device.
- **Publish Joblib externally:** deferred because no authenticated artifact
  release channel and compatibility policy currently exists.
- **Commit Joblib:** rejected for the MVP because it is opaque, executable when
  loaded, version-coupled, and not byte-stable across observed environments.
- **Hand-code the selected rules:** rejected because manual transcription would
  weaken provenance and parity guarantees.
