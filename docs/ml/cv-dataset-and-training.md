# AGM-030 CV dataset and training evidence

The executable contract and operating instructions are maintained in
[`ai/computer_vision/README.md`](../../ai/computer_vision/README.md). This page
records repository-level status without duplicating generated measurements.

- Selected MVP retrieval source: `gabrieldgf4/PlantVillage-Dataset`
- Pinned revision: `825c387b026b01570caa85ab7fdba5cb594adab0`
- Binary target: `NORMAL` / `ANOMALY` only
- Label map, preprocessing, related-group, split, selection, training, and
  artifact-metadata contracts are versioned.
- Exact duplicates stay together; conflicting exact labels fail.
- Same-label perceptual candidates form connected groups; cross-label
  candidates are quarantined.
- Splits are deterministic, group-aware, replayable, and exclude quarantine.
- Baseline and MobileNetV2 decisions use validation only.
- The final test partition and threshold selection are reserved for AGM-031.
- Raw data and large weights are not committed.

The GitHub mirror contains no licence file. Known upstream CC0 provenance is
documented separately from the mirror and is not overstated.

## Pre-commit real-data validation (2026-09-25)

The immutable archive for revision
`825c387b026b01570caa85ab7fdba5cb594adab0` was verified with SHA-256
`ae430d573bda45084545c84d5ca54a830d932962e80f385396956d799d1f254e`.
The audit found 54,305 files: 54,300 accepted, five explicitly excluded,
zero invalid, 105 quarantined, and 54,195 eligible (15,040 `NORMAL`, 39,155
`ANOMALY`). It found 21 exact-duplicate groups (42 images), 441 perceptual
candidate pairs, and 38 cross-label candidates. The dataset fingerprint is
`e7bbae54f67cd2226f565a50d814c63fcc3457024c17ab7730dbd76d4d4d82ae`;
the related-manifest fingerprint is
`a8260d72d8644f26f4cb8f5e33c704088496720ce2cd28df8b19898256814a17`.

The deterministic split contains 37,937 TRAIN, 8,129 VALIDATION, and 8,129
TEST samples. Its fingerprint is
`a22f57a547ff2a7ccb0d9c5539ffa2d036cde6eb95e83865b7c9dc23b6a18acf`.
No eligible perceptual candidate pair crosses partitions.

The validation-only baseline produced macro-F1 0.673099 and accuracy 0.711773.
MobileNetV2 produced macro-F1 0.977649 and accuracy 0.982040 and therefore won
the versioned selection rule. TEST was not evaluated and threshold selection
remains deferred to AGM-031. This is pre-commit validation evidence: the run
records `git_dirty=true`, and generated manifests, model weights, and metadata
remain local and ignored. A distributable official artifact must be regenerated
from the committed clean revision.

## Required limitation

Performance on clean, controlled PlantVillage leaf photographs does not prove
performance on field photographs with natural backgrounds, different lighting,
blur, occlusion, multiple leaves, different cameras, unseen cultivars/species,
or Tunisian farm conditions. The model is visual screening only; it does not
diagnose disease or issue agronomic or irrigation instructions.
