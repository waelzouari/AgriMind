# AGM-030 computer-vision dataset and training pipeline

AGM-030 defines only the binary training labels `NORMAL` (0) and `ANOMALY`
(1). It is a visual-screening model boundary, not disease diagnosis, an
agronomic recommendation, an irrigation decision, an inference API, image
upload, camera integration, robotics, or SLAM.

## Selected MVP dataset and provenance

This corrective implementation selects the PlantVillage retrieval mirror
[`gabrieldgf4/PlantVillage-Dataset`](https://github.com/gabrieldgf4/PlantVillage-Dataset)
at immutable Git revision
`825c387b026b01570caa85ab7fdba5cb594adab0`. The notebook was a technical
reference only and is not evidence that the dataset was previously approved.

The mirror republishes PlantVillage material but has no repository-level
licence file. CC0 1.0 is attributed to the known upstream PlantVillage
distribution; it must not be represented as an independent licence grant by
the mirror. The configuration retains this distinction and the source URL,
revision, authors, paper DOI, archive name, and expected archive checksum.

The versioned map contains 38 explicit source folders: 12 map to `NORMAL` and
26 to `ANOMALY`. Unknown folders fail closed; labels are never inferred from a
`healthy` substring. The five files under `x_Removed_from_Healthy_leaves` are
explicit exclusions.

A real pre-commit audit and validation-only training run was completed on
2026-09-25 from the verified immutable archive. Exact counts, fingerprints,
validation metrics, and the dirty-tree limitation are recorded in
`docs/ml/cv-dataset-and-training.md`. Generated data, manifests, metadata, and
weights remain local and ignored; regenerate any distributable artifact from
the committed clean revision.

## Source verification

Every audit emits `VERIFIED` or `UNVERIFIED` source evidence. Verification may
come from:

- a Git checkout whose `origin` URL and `HEAD` both match the configuration;
- an immutable archive whose SHA-256 matches the configuration; or
- an exact schema-v1 acquisition evidence record containing the configured
  source URL, revision, and archive checksum.

An audit may describe an `UNVERIFIED` source, but official training refuses it.
No Git metadata is fabricated.

Clone the exact source when network access is available:

```bash
git clone --no-checkout https://github.com/gabrieldgf4/PlantVillage-Dataset.git \
  ai/computer_vision/data/raw/plantvillage-notebook-mirror
git -C ai/computer_vision/data/raw/plantvillage-notebook-mirror fetch --depth 1 origin \
  825c387b026b01570caa85ab7fdba5cb594adab0
git -C ai/computer_vision/data/raw/plantvillage-notebook-mirror checkout --detach \
  825c387b026b01570caa85ab7fdba5cb594adab0
```

Raw data and generated detailed evidence remain ignored.

## Audit, grouping, quarantine, and fingerprints

Discovery and manifest ordering use canonical relative paths. The dataset
fingerprint v1 hashes the dataset ID/version, label-map version, sorted mapping,
and for every decoded sample its canonical path, source/binary labels, content
SHA-256, perceptual dHash, dimensions, and channel count. Filesystem enumeration
order cannot change it.

Exact-byte duplicates are grouped by SHA-256 and cannot cross partitions. An
exact duplicate mapped to both labels fails the audit.

The configured dHash threshold produces heuristic visual-similarity candidates:

- same-label candidate relationships form transitive connected components;
- each component receives a deterministic related-group ID and stays intact;
- all samples involved in a cross-label candidate are quarantined with
  `cross_label_near_duplicate_candidate` and cannot enter any split;
- the pipeline fails if an eligible candidate pair crosses partitions.

Perceptual hashing is a conservative heuristic, not proof that photographs show
the same physical leaf. The deterministic JSON Lines related manifest records
path, content/dHash, related group, label, and quarantine state, and has its own
fingerprint.

## Split and test isolation

Split contract `agrimind-cv-group-split-v1` assigns eligible related groups to
`TRAIN`, `VALIDATION`, or `TEST` using the versioned ratios and seed. Inputs are
canonicalized, grouping is indivisible, and quarantined samples are absent. The
JSON Lines manifest can be replayed; a mismatch fails closed.

AGM-030 uses `TRAIN` for fitting and `VALIDATION` for early stopping, checkpoint
selection, metrics, and model selection. `TEST` is never loaded by selection or
evaluation. Metadata requires `test_evaluated: false`; final test evaluation and
threshold trade-off analysis belong to AGM-031.

## Preprocessing, augmentation, and selection

Preprocessing contract `agrimind-cv-mobilenet-v2-preprocessing-v1` means:
deterministic decode to RGB, aspect-preserving bilinear resize plus center crop
to 224×224, float32 CHW output, values scaled by 255, then ImageNet channel mean
and standard-deviation normalization.

Augmentation is training-only. Horizontal flip probability comes from the
training configuration. Each decision is reproducibly derived from global seed,
epoch, and sample identity, so equal runs reproduce the sequence while epochs
may differ. Validation and test never receive augmentation.

The mean-RGB centroid baseline fits `TRAIN` and scores `VALIDATION` before the
frozen-feature MobileNetV2 candidate. Selection rule
`agrimind-cv-validation-selection-v1` compares validation macro-F1, then
validation accuracy, and chooses the baseline on a tie. No test metric or tuned
threshold participates.

## Reproducible commands

Lightweight development and CI dependencies:

```bash
python -m pip install -e "./ai/computer_vision[dev]"
python -m pytest -q -c ai/computer_vision/pyproject.toml ai/computer_vision/tests
```

Pinned Python 3.11 training environment:

```bash
python -m pip install -c ai/computer_vision/training-constraints.txt \
  -e "./ai/computer_vision[train]"
```

Audit example:

```bash
python -m agrimind_cv.cli audit \
  --dataset-config ai/computer_vision/configs/datasets/plantvillage-notebook-mirror-v1.json \
  --dataset-root ai/computer_vision/data/raw/plantvillage-notebook-mirror \
  --audit-report ai/computer_vision/data/interim/audit.json \
  --related-manifest ai/computer_vision/data/interim/related.jsonl
```

Official training additionally requires a training config, split manifest,
artifact path, metadata path, artifact ID, and semantic artifact version. It
fails unless source evidence is `VERIFIED`. Large model files remain ignored;
schema-validated metadata includes their path, size, SHA-256, contracts,
fingerprints, actual Git revision/dirty state, pinned configuration, runtime,
validation evidence, selected model, and explicit test isolation.

## Scientific limitation

Performance measured on clean, controlled PlantVillage leaf images does **not**
demonstrate equivalent performance on real field images. Expected domain shift
includes natural backgrounds, lighting, blur, occlusion, multiple leaves,
camera differences, unseen cultivars or species, and Tunisian farm conditions.
No quantitative field-performance or disease-diagnosis claim is made.

## AGM-031 Phase B1 boundary

The package now owns dependency-light binary metrics, validation-only threshold
selection and strict runtime artifact verification. Threshold selection accepts
only a `ValidationScores` contract; the held-out evaluator requires frozen
model, preprocessing and threshold evidence plus validation/artifact identity.
The runtime constructs MobileNetV2 with `weights=None`, verifies the external
artifact before loading a strict state dict, and never downloads weights.

Official clean weights, the selected threshold and held-out TEST metrics remain
pending Phase B2. No final evaluation result is claimed by the B1 code or tests.
