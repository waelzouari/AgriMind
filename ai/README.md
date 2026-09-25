# AI

Reproducible irrigation and computer-vision work will live in separate
subdirectories with data contracts, configurations, source, tests, and
versioned artifact metadata.

The irrigation boundary now contains the AGM-021 versioned feature contract
and a read-only, offline dataset audit tool. The licensed real dataset remains
ignored under `irrigation/data/raw/`; ordinary CI uses explicitly synthetic
fixtures and does not claim to validate the real workbook. See
[`docs/ai/irrigation-dataset.md`](../docs/ai/irrigation-dataset.md).

AGM-022 adds a deterministic, validation-selected irrigation baseline and its
dataset-specific evaluation. The methodology and measured limitations are in
[`docs/ai/irrigation-baseline.md`](../docs/ai/irrigation-baseline.md). Generated
Joblib model artifacts remain ignored and are not a runtime inference interface.

AGM-023 exports the trusted selected tree into a deterministic, reviewable JSON
artifact packaged by the edge. Joblib remains ignored and is used only as local
training evidence and an export/parity source. Runtime behavior and failure
semantics are documented in
[`docs/ai/irrigation-inference.md`](../docs/ai/irrigation-inference.md).

Tank level, pump status, and sensor status are system state and are excluded
from agronomic ML features. Computer vision is limited to `NORMAL` and
`VISUAL_ANOMALY_DETECTED`; disease diagnosis and robot autonomy are excluded.

AGM-030 adds the separate training label contract `NORMAL` / `ANOMALY`, a
verified-source dataset audit, conservative related-image quarantine, replayable
group-aware splits, a simple baseline, and validation-only MobileNetV2 model
selection. It does not add an inference API or alter the established downstream
event vocabulary. See
[`computer_vision/README.md`](computer_vision/README.md).
