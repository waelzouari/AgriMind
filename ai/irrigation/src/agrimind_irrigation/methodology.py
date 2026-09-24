"""Versioned AGM-022 methodology, deterministic preparation, and temporal split."""

from __future__ import annotations

import json
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

from agrimind_irrigation.audit import AuditReport, audit_dataset, read_dataset_rows
from agrimind_irrigation.contract import FeatureContract

DEFAULT_RANDOM_SEED = 42
ORDERED_FEATURES = (
    "soil_moisture_index_0_100",
    "air_temperature_c",
    "air_relative_humidity_percent",
)
FORBIDDEN_MODEL_INPUTS = frozenset(
    {
        "Time",
        "irrigation",
        "best time",
        "Soil Tempertuer",
        "crop type",
        "row",
        "index",
        "weather",
        "tank level",
        "ADC raw",
    }
)
_EXCEL_1900_PRE_LEAP_BUG_EPOCH = datetime(1899, 12, 31)
_EXCEL_1900_POST_LEAP_BUG_EPOCH = datetime(1899, 12, 30)


class MethodologyError(ValueError):
    """Methodology configuration is invalid."""


class DatasetValidationError(ValueError):
    """Dataset identity, schema, or content is invalid."""


class SplitValidationError(ValueError):
    """The configured chronological split is unusable."""


@dataclass(frozen=True, slots=True)
class Methodology:
    version: str
    feature_contract_version: str
    dataset_sha256: str
    random_seed: int
    validation_start: datetime
    test_start: datetime
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TrainingRow:
    source_row: int
    observed_at: datetime
    features: tuple[float, float, float]
    target: int


@dataclass(frozen=True, slots=True)
class InvalidRow:
    source_row: int
    observed_at: datetime
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedDataset:
    rows: tuple[TrainingRow, ...]
    invalid_rows: tuple[InvalidRow, ...]
    audit: AuditReport


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    train: tuple[TrainingRow, ...]
    validation: tuple[TrainingRow, ...]
    test: tuple[TrainingRow, ...]


def load_methodology(path: Path) -> Methodology:
    raw = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    split = raw.get("split")
    if not isinstance(split, dict):
        raise MethodologyError("split must be an object")
    if raw.get("methodology_version") != "baseline-v1":
        raise MethodologyError("methodology_version must be baseline-v1")
    if raw.get("feature_contract_version") != "v1":
        raise MethodologyError("feature_contract_version must be v1")
    if raw.get("invalid_row_policy") != "drop":
        raise MethodologyError("invalid_row_policy must be drop")
    seed = raw.get("random_seed")
    if seed != DEFAULT_RANDOM_SEED:
        raise MethodologyError(f"random_seed must be {DEFAULT_RANDOM_SEED}")
    if split.get("strategy") != "calendar_chronological":
        raise MethodologyError("split strategy must be calendar_chronological")
    if split.get("timestamps") != "naive_excel_1900":
        raise MethodologyError("split timestamps must be naive_excel_1900")
    try:
        validation_start = datetime.fromisoformat(str(split["validation_start"]))
        test_start = datetime.fromisoformat(str(split["test_start"]))
    except (KeyError, ValueError) as error:
        raise MethodologyError("split boundaries must be ISO-8601 datetimes") from error
    if validation_start.tzinfo is not None or test_start.tzinfo is not None:
        raise MethodologyError("split boundaries must be naive")
    if validation_start >= test_start:
        raise MethodologyError("validation boundary must precede test boundary")
    return Methodology(
        version="baseline-v1",
        feature_contract_version="v1",
        dataset_sha256=str(raw.get("dataset_sha256", "")).upper(),
        random_seed=DEFAULT_RANDOM_SEED,
        validation_start=validation_start,
        test_start=test_start,
        raw=raw,
    )


def validate_feature_contract(contract: FeatureContract, methodology: Methodology) -> None:
    if contract.version != methodology.feature_contract_version:
        raise MethodologyError("feature contract version does not match methodology")
    if contract.dataset_sha256 != methodology.dataset_sha256:
        raise MethodologyError("dataset fingerprint does not match methodology")
    if tuple(feature.canonical_name for feature in contract.ordered_features) != ORDERED_FEATURES:
        raise MethodologyError("ordered model features do not match Feature Contract V1")
    if contract.target_name != "irrigation_required" or contract.target_values != {0, 1}:
        raise MethodologyError("target contract does not match Feature Contract V1")


def validate_model_feature_names(names: tuple[str, ...]) -> None:
    if any(name in FORBIDDEN_MODEL_INPUTS for name in names):
        raise MethodologyError("forbidden leakage or metadata column used as model input")
    if names != ORDERED_FEATURES:
        raise MethodologyError("model input must use the exact Feature Contract V1 order")


def _assert_excel_1900(path: Path) -> None:
    if path.suffix.lower() != ".xlsx":
        return
    try:
        with zipfile.ZipFile(path) as archive:
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise DatasetValidationError("dataset is not a readable XLSX package") from error
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    properties = workbook.find(f"{namespace}workbookPr")
    date_1904 = properties is not None and properties.attrib.get("date1904") in {"1", "true"}
    if date_1904:
        raise DatasetValidationError("AGM-022 requires the Excel 1900 date system")


def _finite_number(value: object | None) -> float | None:
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: object | None) -> datetime:
    number = _finite_number(value)
    if number is None:
        raise DatasetValidationError("Time must contain finite Excel serial dates")
    # Excel incorrectly treats 1900 as a leap year. Serial 60 is the fictitious
    # 1900-02-29; later dates need the extra one-day offset used by the workbook.
    epoch = _EXCEL_1900_PRE_LEAP_BUG_EPOCH if number < 60 else _EXCEL_1900_POST_LEAP_BUG_EPOCH
    return epoch + timedelta(days=number)


def prepare_dataset(
    contract: FeatureContract,
    methodology: Methodology,
    dataset_path: Path,
    *,
    expected_sha256: str,
) -> PreparedDataset:
    """Validate, filter, and chronologically order an immutable source dataset."""

    validate_feature_contract(contract, methodology)
    validate_model_feature_names(ORDERED_FEATURES)
    if expected_sha256.upper() != methodology.dataset_sha256:
        raise DatasetValidationError("expected fingerprint does not match methodology")
    _assert_excel_1900(dataset_path)
    audit = audit_dataset(contract, dataset_path, expected_sha256=expected_sha256)
    if not audit.fingerprint_matches or not audit.structurally_valid:
        raise DatasetValidationError("dataset fingerprint or schema is invalid")
    columns, raw_rows = read_dataset_rows(dataset_path, contract.sheet_name)
    indices = {name: index for index, name in enumerate(columns)}
    feature_columns = tuple(feature.dataset_column for feature in contract.ordered_features)
    required = ("Time", *feature_columns, contract.target_column)
    if any(column not in indices for column in required):
        raise DatasetValidationError("dataset is missing a required training column")

    usable: list[TrainingRow] = []
    invalid: list[InvalidRow] = []
    for source_row, row in enumerate(raw_rows, start=2):
        observed_at = _timestamp(row[indices["Time"]])
        reasons: list[str] = []
        values: list[float] = []
        for feature in contract.ordered_features:
            value = _finite_number(row[indices[feature.dataset_column]])
            if value is None:
                reasons.append(f"invalid_or_missing:{feature.dataset_column}")
                values.append(0.0)
                continue
            if (feature.minimum is not None and value < feature.minimum) or (
                feature.maximum is not None and value > feature.maximum
            ):
                reasons.append(f"out_of_range:{feature.dataset_column}")
            values.append(value)
        target_number = _finite_number(row[indices[contract.target_column]])
        target: int | None = None
        if (
            target_number is None
            or not target_number.is_integer()
            or int(target_number) not in contract.target_values
        ):
            reasons.append(f"invalid_or_missing:{contract.target_column}")
        else:
            target = int(target_number)
        if reasons:
            invalid.append(InvalidRow(source_row, observed_at, tuple(reasons)))
            continue
        assert target is not None
        usable.append(
            TrainingRow(
                source_row,
                observed_at,
                cast(tuple[float, float, float], tuple(values)),
                target,
            )
        )
    usable.sort(key=lambda item: item.observed_at)
    if len(invalid) != audit.invalid_training_rows:
        raise DatasetValidationError("preparation and audit invalid-row counts disagree")
    return PreparedDataset(tuple(usable), tuple(invalid), audit)


def split_dataset(dataset: PreparedDataset, methodology: Methodology) -> DatasetSplit:
    train = tuple(row for row in dataset.rows if row.observed_at < methodology.validation_start)
    validation = tuple(
        row
        for row in dataset.rows
        if methodology.validation_start <= row.observed_at < methodology.test_start
    )
    test = tuple(row for row in dataset.rows if row.observed_at >= methodology.test_start)
    split = DatasetSplit(train, validation, test)
    _validate_split(dataset, split)
    return split


def _validate_split(dataset: PreparedDataset, split: DatasetSplit) -> None:
    partitions = (split.train, split.validation, split.test)
    if any(not partition for partition in partitions):
        raise SplitValidationError("train, validation, and test must be non-empty")
    if tuple((*split.train, *split.validation, *split.test)) != dataset.rows:
        raise SplitValidationError("all usable rows must be assigned exactly once in order")
    if not (
        split.train[-1].observed_at < split.validation[0].observed_at
        and split.validation[-1].observed_at < split.test[0].observed_at
    ):
        raise SplitValidationError("chronological partitions overlap or are out of order")
    for name, partition in zip(("train", "validation", "test"), partitions, strict=True):
        if {row.target for row in partition} != {0, 1}:
            raise SplitValidationError(f"{name} must contain both target classes")


def _feature_counts(rows: tuple[TrainingRow, ...]) -> Counter[tuple[float, ...]]:
    return Counter(row.features for row in rows)


def dataset_diagnostics(dataset: PreparedDataset, split: DatasetSplit) -> dict[str, Any]:
    partitions = {"train": split.train, "validation": split.validation, "test": split.test}
    counts = {name: _feature_counts(rows) for name, rows in partitions.items()}
    overlaps: dict[str, dict[str, int]] = {}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        vectors = counts[left].keys() & counts[right].keys()
        overlaps[f"{left}_{right}"] = {
            "unique_vectors": len(vectors),
            f"{left}_rows": sum(counts[left][vector] for vector in vectors),
            f"{right}_rows": sum(counts[right][vector] for vector in vectors),
            "total_rows": sum(counts[left][vector] + counts[right][vector] for vector in vectors),
        }

    targets: dict[tuple[float, ...], set[int]] = defaultdict(set)
    vector_counts: Counter[tuple[float, ...]] = Counter()
    for row in dataset.rows:
        targets[row.features].add(row.target)
        vector_counts[row.features] += 1
    conflicting = {vector for vector, labels in targets.items() if labels == {0, 1}}
    conflict_partitions = {
        name: sum(row.features in conflicting for row in rows) for name, rows in partitions.items()
    }
    return {
        "feature_only": {
            "unique_vectors": len(targets),
            "repeated_vectors": sum(count > 1 for count in vector_counts.values()),
            "target_0_only_vectors": sum(labels == {0} for labels in targets.values()),
            "target_1_only_vectors": sum(labels == {1} for labels in targets.values()),
            "conflicting_label_vectors": len(conflicting),
            "conflicting_label_rows": sum(vector_counts[vector] for vector in conflicting),
            "conflicting_rows_by_partition": conflict_partitions,
        },
        "feature_only_overlap": overlaps,
    }


def split_summary(split: DatasetSplit) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, rows in (
        ("train", split.train),
        ("validation", split.validation),
        ("test", split.test),
    ):
        targets = Counter(row.target for row in rows)
        result[name] = {
            "rows": len(rows),
            "class_counts": {"0": targets[0], "1": targets[1]},
            "positive_rate": targets[1] / len(rows),
            "first_timestamp": rows[0].observed_at.isoformat(),
            "last_timestamp": rows[-1].observed_at.isoformat(),
        }
    return result


def methodology_to_dict(methodology: Methodology) -> dict[str, Any]:
    return asdict(methodology)
