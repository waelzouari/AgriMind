"""Strict JSON configuration loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agrimind_cv.contracts import CanonicalLabel


class ConfigurationError(ValueError):
    """Configuration is missing, malformed, or scientifically unsafe."""


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    schema_version: int
    dataset_id: str
    dataset_version: str
    source_url: str
    source_revision: str
    doi: str
    authors: tuple[str, ...]
    license_id: str
    archive_name: str
    archive_sha256: str | None
    label_mapping: dict[str, CanonicalLabel]
    excluded_source_labels: frozenset[str]
    supported_extensions: frozenset[str]
    grouping_key: str | None
    known_limitations: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> DatasetConfig:
        try:
            raw = _object(json.loads(path.read_text(encoding="utf-8")), "config")
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigurationError("dataset configuration is unreadable") from error
        required = {
            "schema_version",
            "dataset_id",
            "dataset_version",
            "source_url",
            "source_revision",
            "doi",
            "authors",
            "license",
            "archive",
            "label_mapping",
            "excluded_source_labels",
            "supported_extensions",
            "grouping_key",
            "known_limitations",
        }
        if raw.keys() != required:
            raise ConfigurationError("dataset configuration fields do not match schema v1")
        if raw["schema_version"] != 1:
            raise ConfigurationError("unsupported dataset configuration version")
        license_data = _object(raw["license"], "license")
        archive = _object(raw["archive"], "archive")
        license_id = str(license_data.get("id", "")).strip()
        if not license_id or not str(license_data.get("url", "")).startswith("https://"):
            raise ConfigurationError("verified license ID and URL are required")
        mapping_raw = _object(raw["label_mapping"], "label_mapping")
        try:
            mapping = {key: CanonicalLabel(value) for key, value in mapping_raw.items()}
        except ValueError as error:
            raise ConfigurationError("label mapping contains an unsupported target") from error
        if not mapping or set(mapping.values()) != set(CanonicalLabel):
            raise ConfigurationError("label mapping must cover both canonical labels")
        excluded_raw = raw["excluded_source_labels"]
        if not isinstance(excluded_raw, list) or any(
            not isinstance(item, str) or not item.strip() for item in excluded_raw
        ):
            raise ConfigurationError("excluded_source_labels must be a list of non-empty strings")
        excluded = frozenset(item.strip() for item in excluded_raw)
        if excluded.intersection(mapping):
            raise ConfigurationError("included and excluded source labels must not overlap")
        extensions = frozenset(str(item).lower() for item in raw["supported_extensions"])
        if not extensions or any(not item.startswith(".") for item in extensions):
            raise ConfigurationError("supported extensions must be dot-prefixed")
        grouping = raw["grouping_key"]
        if grouping is not None and not isinstance(grouping, str):
            raise ConfigurationError("grouping_key must be a string or null")
        authors = tuple(str(item).strip() for item in raw["authors"])
        limitations = tuple(str(item).strip() for item in raw["known_limitations"])
        if not all(authors) or not limitations:
            raise ConfigurationError("authors and known limitations are required")
        return cls(
            schema_version=1,
            dataset_id=str(raw["dataset_id"]),
            dataset_version=str(raw["dataset_version"]),
            source_url=str(raw["source_url"]),
            doi=str(raw["doi"]),
            authors=authors,
            license_id=license_id,
            archive_name=str(archive.get("name", "")),
            source_revision=str(raw["source_revision"]),
            archive_sha256=(
                str(archive["sha256"]).lower() if archive.get("sha256") is not None else None
            ),
            label_mapping=mapping,
            excluded_source_labels=excluded,
            supported_extensions=extensions,
            grouping_key=grouping,
            known_limitations=limitations,
        )


@dataclass(frozen=True, slots=True)
class SplitConfig:
    train: float
    validation: float
    test: float
    seed: int
    require_group_ids: bool = True

    def __post_init__(self) -> None:
        values = (self.train, self.validation, self.test)
        if any(value <= 0 or value >= 1 for value in values):
            raise ConfigurationError("split ratios must be between zero and one")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ConfigurationError("split ratios must sum to one")
        if self.seed < 0:
            raise ConfigurationError("split seed must be non-negative")
