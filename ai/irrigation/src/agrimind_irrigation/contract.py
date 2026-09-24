"""Load and validate the versioned AGM-021 feature contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class Feature:
    canonical_name: str
    dataset_column: str
    runtime_source: str
    scalar_type: str
    unit: str
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class ExcludedColumn:
    classification: str
    reason: str


@dataclass(frozen=True, slots=True)
class FeatureContract:
    version: str
    dataset_sha256: str
    sheet_name: str
    ordered_features: tuple[Feature, ...]
    target_name: str
    target_column: str
    target_values: frozenset[int]
    metadata_columns: tuple[str, ...]
    excluded_columns: dict[str, ExcludedColumn]

    @property
    def required_columns(self) -> tuple[str, ...]:
        return (
            *self.metadata_columns,
            *(f.dataset_column for f in self.ordered_features),
            self.target_column,
        )

    @property
    def allowed_columns(self) -> frozenset[str]:
        return frozenset((*self.required_columns, *self.excluded_columns))


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, Any], value)


def load_contract(path: Path) -> FeatureContract:
    """Load a contract while enforcing the immutable V1 order and encoding."""

    raw = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if raw.get("contract_version") != "v1":
        raise ValueError("contract_version must be v1")
    dataset = _object(raw.get("dataset"), "dataset")
    feature_rows = raw.get("ordered_features")
    if not isinstance(feature_rows, list):
        raise ValueError("ordered_features must be a list")
    features: list[Feature] = []
    for row_value in feature_rows:
        row = _object(row_value, "ordered feature")
        valid_range = row.get("valid_range")
        minimum: float | None = None
        maximum: float | None = None
        if valid_range is not None:
            bounds = _object(valid_range, "valid_range")
            minimum = float(bounds["minimum"])
            maximum = float(bounds["maximum"])
        features.append(
            Feature(
                canonical_name=str(row["canonical_name"]),
                dataset_column=str(row["dataset_column"]),
                runtime_source=str(row["runtime_source"]),
                scalar_type=str(row["scalar_type"]),
                unit=str(row["unit"]),
                minimum=minimum,
                maximum=maximum,
            )
        )
    expected_order = (
        "soil_moisture_index_0_100",
        "air_temperature_c",
        "air_relative_humidity_percent",
    )
    if tuple(feature.canonical_name for feature in features) != expected_order:
        raise ValueError("V1 ordered feature vector does not match the approved order")
    target = _object(raw.get("target"), "target")
    encoding = _object(target.get("encoding"), "target.encoding")
    if encoding != {"0": False, "1": True}:
        raise ValueError("V1 target encoding must be 0=false and 1=true")
    excluded_values = raw.get("excluded_columns")
    if not isinstance(excluded_values, list):
        raise ValueError("excluded_columns must be a list")
    excluded: dict[str, ExcludedColumn] = {}
    for value in excluded_values:
        row = _object(value, "excluded column")
        if row.get("dataset_column") is not None:
            excluded[str(row["dataset_column"])] = ExcludedColumn(
                classification=str(row["classification"]),
                reason=str(row["reason"]),
            )
    return FeatureContract(
        version="v1",
        dataset_sha256=str(dataset["primary_file_sha256"]).upper(),
        sheet_name=str(dataset["sheet_name"]),
        ordered_features=tuple(features),
        target_name=str(target["canonical_name"]),
        target_column=str(target["source_column"]),
        target_values=frozenset({0, 1}),
        metadata_columns=tuple(str(value) for value in raw.get("metadata_columns", [])),
        excluded_columns=excluded,
    )
