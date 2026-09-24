# AGM-021 irrigation dataset and feature contract

> AGM-021 MVP provisional data contract policy — subject to later field
> calibration and validation with AgriMind hardware.

## Dataset identity and storage

The approved MVP source is **Mendeley Irrigation-Dataset**, version 1, published
under CC BY 4.0 with DOI `10.17632/67gkrzbwrr.1`. The primary workbook is
`second dataset collected.xlsx`; the audited file has SHA-256:

```text
F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D
```

The downloaded archive and workbook remain outside Git under
`ai/irrigation/data/raw/`. CI uses only synthetic fixtures marked as non-real
agricultural data. Passing fixture tests validates the audit boundary, not the
real dataset. Attribution metadata is retained in the versioned contract.

The primary filename, workbook schema, row count, and SHA-256 are locally
verified. The logical name, DOI, version, CC BY 4.0 licence, contributor,
collection location, and publication date are externally documented by the
Mendeley record; they are not embedded as a README or licence file in the local
download package.

The target interpretation is additionally informed by *Hybrid Artificial
Neural Network Activation Function to Reduce Water Wastage in Agricultural
Irrigation*, IEEE Access (2025), DOI `10.1109/ACCESS.2025.3573678`. No model
quality or agronomic result from that publication is claimed here.

## Feature and target contract

[`feature-contract-v1.json`](../../ai/irrigation/data_contracts/feature-contract-v1.json)
is authoritative. Its feature vector is ordered and must never be derived from
a mapping or source-column order:

1. `soil_moisture_index_0_100`
2. `air_temperature_c`
3. `air_relative_humidity_percent`

The source dataset describes `irrigation` as observed irrigation status ON/OFF,
encoded as `0 = OFF` and `1 = ON`. The MVP contract provisionally interprets
that source status as target `irrigation_required`, where `0 = false` and
`1 = true`, to produce a requirement estimate before physical actuation. This
reinterpretation is part of the provisional policy; the dataset does not prove
that the label is a universal agronomic need. A prediction is only a
recommendation and never a pump command: future inference feeds an independent
Raspberry Pi safety gate, which remains authoritative.

Required feature or target values that are missing, non-finite, incorrectly
typed, outside a contractual range, or outside the target encoding make that
training row invalid. AGM-021 reports such rows without modifying or imputing
them. AGM-022 owns preprocessing decisions.

## Soil-moisture proxy limitation

The source dataset does not provide the physical calibration of `Soil
Moisture`. V1 therefore treats it as a normalized 0–100 soil-moisture index,
not as a portable metrological percentage. AgriMind runtime
`SensorSnapshot.soil_humidity` is also normalized to 0–100, but comes from a
different ADS1115 calibration.

No metrological or agronomic equivalence is claimed. This proxy supports an
MVP functional demonstration only. Before production, the model must be
recalibrated or retrained using field data captured with AgriMind hardware.

## Explicit exclusions and leakage

- `best time`: known leakage and forbidden as a feature. In the audited file,
  every occurrence with `best time = 1` also has `irrigation = 1`; exclusion
  is contractual and does not depend on reproducing that correlation.
- `Soil Tempertuer`: no corresponding AgriMind runtime sensor.
- `crop type`: undocumented codes `1/2` and no stable runtime contract.
- `Time`: audit and future split metadata only.
- AGM-019 weather: out of model V1 to avoid training-serving skew and a network
  dependency.
- tank level: system/safety state, not an agronomic feature.
- raw soil ADC: calibration-specific.
- farm, device, and correlation IDs: grouping/traceability metadata only.

## Audited observations and split guidance

The real workbook contains 3,589 rows sampled at approximately three-minute
intervals over about one week. Five rows are invalid for V1 training because a
required feature or target is missing. Of 3,588 labelled rows, 2,997 carry `0`
and 591 carry `1`, a majority/minority ratio of about 5.07:1.

No exact rows repeat when `Time` is included. Excluding `Time`, the audit finds
2,343 duplicate rows; the three-feature-plus-target vector contains 2,627
duplicate rows. The temporal density and repetition make random row splitting
high risk. AGM-022 must choose the time/group split, imbalance treatment,
preprocessing, baseline, metrics, and evaluation method.

The workbook stores `Time` as Excel serial dates. AGM-021 preserves those raw
cell values only for identity, duplicate exclusion, and future ordering; it
does not convert them to UTC or invent a timezone. The XLSX 1900/1904 date
system is deliberately not interpreted by this audit because `Time` is not a
V1 feature. AGM-022 must interpret the workbook date system explicitly before
using time for a split.

## Validity and exit-code policy

`structurally_valid` means that the file is readable, its raw-file fingerprint
matches, and required/unexpected columns satisfy the contract. It does **not**
mean every row is usable for training. `invalid_training_rows` separately
counts rows with a missing, non-finite, mistyped, out-of-range feature or an
absent/invalid target. The real dataset is structurally valid but contains five
invalid training rows; AGM-022 must decide how to handle them.

The CLI exits non-zero for an unreadable/malformed file, unsupported contract
version or target encoding, fingerprint mismatch, missing required column, or
unexpected column. It exits zero when the structure is valid even if individual
training rows are invalid, because the audit reports rather than preprocesses
raw data. Consumers must inspect `invalid_training_rows` before training.

AGM-022's filtering, chronological split, baseline selection, measured results,
and limitations are documented in
[`irrigation-baseline.md`](irrigation-baseline.md). Feature Contract V1 remains
unchanged.

## Audit boundaries

Install the local package, then audit the ignored workbook explicitly:

```powershell
python -m pip install -e "./ai/irrigation[dev]"
python -m agrimind_irrigation.audit `
  --contract ai/irrigation/data_contracts/feature-contract-v1.json `
  --dataset "ai/irrigation/data/raw/mendeley-irrigation-v1/Irrigation-Dataset/second dataset collected.xlsx" `
  --expected-sha256 F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D
```

The auditor is deterministic, read-only, standard-library-only, offline,
hardware-free, and reports aggregates without dumping dataset rows. It supports
the real XLSX boundary and synthetic CSV contract fixtures. It performs no
training, splitting, imputation, deduplication, MQTT, GPIO, pump, or irrigation
mode operation.
