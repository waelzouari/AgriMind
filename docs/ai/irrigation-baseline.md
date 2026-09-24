# AGM-022 irrigation baseline methodology and evaluation

## Scope and evidence boundary

AGM-022 measures baseline classification performance on the audited Mendeley
Irrigation-Dataset version 1 under the chronological split below. It does not
establish agronomic validity, production reliability, water savings, or
performance on AgriMind field hardware.

The source workbook is `second dataset collected.xlsx`, DOI
`10.17632/67gkrzbwrr.1`, under CC BY 4.0. Its verified SHA-256 is
`F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D`.
The real workbook remains ignored under `ai/irrigation/data/raw/`.

## Contract and preparation

The immutable Feature Contract V1 supplies exactly this ordered vector:

1. `soil_moisture_index_0_100`
2. `air_temperature_c`
3. `air_relative_humidity_percent`

The target is provisional `irrigation_required`, encoded `0 = false` and
`1 = true`. A prediction is a recommendation, not a physical command.

Features and irrigation status occur in the same source record. Feature
availability before an irrigation decision is assumed for this MVP, but the
dataset does not independently establish their causal pre-actuation ordering.
In particular, a simultaneous soil-moisture measurement may already be
affected by irrigation that is on. This experiment can therefore reconstruct
status associations; it does not validate causality.

The pipeline verifies the dataset fingerprint and schema, interprets `Time`
using the workbook's Excel 1900 date system, retains naïve timestamps, sorts
oldest to newest, and drops invalid training rows without modifying or
imputing the source. Five of 3,589 rows are excluded: three lack humidity, one
lacks both soil moisture and target, and one lacks temperature. The resulting
3,584 rows contain 2,994 zeros and 590 ones.

`best time`, `Time`, `irrigation`, `Soil Tempertuer`, `crop type`, identifiers,
weather, tank level, raw ADC values, and post-action data are never model
features. No rows are deduplicated.

## Chronological split and drift

| Partition | Naïve workbook-time boundary | Rows | Class 0 | Class 1 | Positive rate |
|---|---|---:|---:|---:|---:|
| Train | before 2023-01-04 | 2,320 | 2,200 | 120 | 5.17% |
| Validation | 2023-01-04 | 480 | 384 | 96 | 20.00% |
| Test | from 2023-01-05 | 784 | 410 | 374 | 47.70% |

The large target-rate change is retained. Results therefore measure temporal
generalization under strong distribution shift. A random row split was not
used.

The audit reports no exact duplicate when `Time` is included, 2,343 duplicate
rows without `Time`, and 2,627 duplicate feature-plus-target rows. Feature-only
analysis finds 956 unique vectors, of which 418 repeat. Forty-one vectors
overlap train/validation and cover 1,116 rows; none overlap train/test; eight
overlap validation/test and cover 74 rows.

Two feature vectors have both labels, covering four rows: three in train and
one in validation. These observations are retained. They show that identical
three-value measurements do not always determine a unique source label.

## Models and selection

The experiment uses seed 42 and evaluates 40 configurations:

- majority dummy predicting class 0;
- StandardScaler plus Logistic Regression, with `C` 0.1, 1, or 10;
- bounded Decision Tree depths 2, 3, or 5;
- compact Random Forests with 50 or 100 trees and depth 3 or 5.

Supported candidates compare no class weighting with `balanced`. Tree minimum
leaf sizes are 5, 20, and 50; forest leaf sizes are 5 and 20. Forest execution
uses `n_jobs=1`. No sampling or SMOTE is used.

Every estimator is fit only on train. Thresholds are selected only from
validation probabilities by maximum positive F1, then balanced accuracy, then
distance from 0.5, then the lower numerical threshold. Model selection uses
validation positive F1, validation balanced accuracy, and exact-tie simplicity
in that order. The final estimator is not refit on train plus validation.

Primary metrics are positive-class F1 and balanced accuracy. Secondary metrics
are positive precision/recall, average precision, ROC AUC, accuracy, confusion
matrix, and predicted-positive rate. All zero divisions are reported as zero.

## Measured results

The dummy validation result is 80.00% accuracy, 50.00% balanced accuracy, and
zero positive F1. On test it gives 52.30% accuracy, 50.00% balanced accuracy,
zero positive F1, and `[TN=410, FP=0, FN=374, TP=0]`.

Best validation result by family:

| Family | Configuration summary | Threshold | Positive F1 | Balanced accuracy |
|---|---|---:|---:|---:|
| Logistic Regression | C=0.1, unweighted | 0.0551668 | 0.945652 | 0.951823 |
| Decision Tree | depth=2, leaf=5, unweighted | 0.0204082 | 1.000000 | 1.000000 |
| Random Forest | 50 trees, depth=3, leaf=5, balanced | 0.635490 | 1.000000 | 1.000000 |

The predeclared simplicity rule selects the unweighted Decision Tree with
`max_depth=2` and `min_samples_leaf=5`. At threshold `0.02040816326530612`, its
validation matrix is `[TN=384, FP=0, FN=0, TP=96]`.

The exact train-fitted rules are:

- soil moisture `<= 49.5`, then `<= 44.0`: leaf counts `[96 class 0, 2 class 1]`;
- soil moisture `<= 49.5`, then `> 44.0`: `[6, 94]`;
- soil moisture `> 49.5` and temperature `<= 23.5`: `[2085, 6]`;
- soil moisture `> 49.5` and temperature `> 23.5`: `[13, 18]`.

Decision-tree scores are empirical class frequencies in train leaves, not
validated irrigation probabilities. The selected threshold is exactly the
positive frequency `2/98 = 0.020408...` of the first leaf. Validation contains
29 positive observations in that leaf, so including it changes validation F1
from `0.822086` at threshold 0.5 to `1.0`. At threshold 0.5, test F1 is
`0.795491` with `[TN=410, FP=0, FN=127, TP=247]`; threshold tuning is therefore
material rather than cosmetic.

Twenty-four of the 40 configurations reach perfect validation F1 and balanced
accuracy (12 trees and 12 forests). Selection among them is consequently not
strong evidence for one model family; the predeclared simplicity tie-break
selects the first least-complex tree.

That same train-only fitted tree is evaluated once on test, without refit. The
measured test metrics are:

- accuracy: 1.0;
- balanced accuracy: 1.0;
- positive precision, recall, and F1: 1.0;
- average precision and ROC AUC: 1.0;
- predicted-positive rate: 0.4770408163;
- confusion matrix: `[TN=410, FP=0, FN=0, TP=374]`.

These perfect dataset-specific values are not evidence of general real-world
performance. The short collection period, repeated observations, abrupt label
distribution shift, feature/label conflicts, provisional target semantics, and
undocumented sensor and crop-code meanings materially limit interpretation.
The evidence covers only about 7.5 days from one public dataset/site and two
undocumented crop codes; it is not independent multi-site validation.
They are consistent with reconstruction of a simple deterministic or
near-deterministic irrigation-status relationship in this dataset, especially
the validation/test separation at soil moisture 49.5. They must not be
interpreted as evidence of real-world agronomic generalization. No independent
farm or site validation exists.

## Artifact and reproducibility

[`baseline-v1.json`](../../ai/irrigation/methodologies/baseline-v1.json) fixes
the methodology. The machine-readable evaluation is
[`baseline-v1.json`](../../ai/irrigation/evaluation/baseline-v1.json).

The experiment writes the selected train-only estimator to the ignored local
path `ai/irrigation/artifacts/baseline-v1.joblib`. Its measured SHA-256 for this
run is `834B978C039F13F8252D62E40C2889C5F1E87F2518C31064E05C2E25F7D7C2B3`.
Joblib byte identity is not promised across library versions or platforms.
Only trusted project-produced artifacts may be loaded. AGM-022 provides no
general artifact loader; AGM-023 owns the runtime/distribution decision.

## Safety and non-claims

The AGM-022 boundary ends at a recommendation:

```text
features → preprocessing → model → probability/class → recommendation
```

It adds no MQTT message, GPIO access, pump command, automatic irrigation, or
safety-gate change. Any later actuation remains subject to an independent local
safety gate. Raspberry Pi latency, RAM, and artifact footprint are **not
measured**.
