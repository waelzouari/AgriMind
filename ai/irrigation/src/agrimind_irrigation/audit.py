"""Deterministic, read-only CSV/XLSX dataset audit for AGM-021."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from agrimind_irrigation.contract import FeatureContract, load_contract

_SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass(frozen=True, slots=True)
class NumericStats:
    minimum: float
    maximum: float
    mean: float
    median: float


@dataclass(frozen=True, slots=True)
class AuditReport:
    contract_version: str
    dataset_sha256: str
    row_count: int
    column_count: int
    columns: tuple[str, ...]
    missing_counts: dict[str, int]
    invalid_training_rows: int
    invalid_type_counts: dict[str, int]
    invalid_range_counts: dict[str, int]
    invalid_target_count: int
    target_counts: dict[str, int]
    target_proportions: dict[str, float]
    exact_duplicate_rows: int
    duplicates_without_time: int
    feature_target_duplicate_rows: int
    numeric_ranges: dict[str, NumericStats]
    known_leakage_columns: tuple[str, ...]
    missing_required_columns: tuple[str, ...]
    unexpected_columns: tuple[str, ...]
    fingerprint_matches: bool
    structurally_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _column_index(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference)
    if match is None:
        raise ValueError("invalid XLSX cell reference")
    value = 0
    for character in match.group():
        value = value * 26 + ord(character) - 64
    return value - 1


def _normalized_xlsx_target(target: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(target.lstrip("/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("XLSX relationship target escapes the package")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("XLSX relationship target is empty")
    return str(PurePosixPath(*parts))


def _parse_xlsx_rows(
    path: Path, expected_sheet: str
) -> tuple[list[str], list[list[object | None]]]:
    archive = zipfile.ZipFile(path)
    with archive:
        names = frozenset(archive.namelist())
        required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
        if not required.issubset(names):
            raise ValueError("XLSX package is missing workbook metadata")
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships.findall(f"{_PACKAGE_REL_NS}Relationship")
        }
        sheet_path: str | None = None
        for sheet in workbook.findall(f".//{_SHEET_NS}sheet"):
            if sheet.attrib["name"] == expected_sheet:
                target = targets[sheet.attrib[f"{_REL_NS}id"]]
                sheet_path = _normalized_xlsx_target(
                    target if target.startswith(("xl/", "/xl/")) else f"xl/{target}"
                )
                break
        if sheet_path is None or sheet_path not in names:
            raise ValueError(f"expected XLSX sheet is missing: {expected_sheet}")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            strings = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in strings.findall(f"{_SHEET_NS}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{_SHEET_NS}t")))
        sheet = ElementTree.fromstring(archive.read(sheet_path))
        parsed: list[dict[int, object | None]] = []
        for row in sheet.findall(f".//{_SHEET_NS}sheetData/{_SHEET_NS}row"):
            values: dict[int, object | None] = {}
            for cell in row.findall(f"{_SHEET_NS}c"):
                index = _column_index(cell.attrib["r"])
                raw = cell.find(f"{_SHEET_NS}v")
                value: object | None = None if raw is None else raw.text
                cell_type = cell.attrib.get("t")
                if cell_type == "s" and value is not None:
                    value = shared[int(str(value))]
                elif cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter(f"{_SHEET_NS}t"))
                elif value is not None:
                    try:
                        number = float(str(value))
                        value = int(number) if number.is_integer() else number
                    except ValueError:
                        pass
                values[index] = value
            if values:
                parsed.append(values)
        if not parsed:
            raise ValueError("dataset contains no rows")
        used_indices = sorted(
            index
            for index in {key for row in parsed for key in row}
            if any(not _missing(row.get(index)) for row in parsed)
        )
        if not used_indices:
            raise ValueError("dataset contains no populated columns")
        header = [str(parsed[0].get(index, "")).strip() for index in used_indices]
        rows = [[row.get(index) for index in used_indices] for row in parsed[1:]]
        return header, rows


def _xlsx_rows(path: Path, expected_sheet: str) -> tuple[list[str], list[list[object | None]]]:
    try:
        return _parse_xlsx_rows(path, expected_sheet)
    except ValueError:
        raise
    except (OSError, KeyError, IndexError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ValueError("dataset is not a readable XLSX package") from error


def _csv_rows(path: Path) -> tuple[list[str], list[list[object | None]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            raw_rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError("dataset is not a readable UTF-8 CSV file") from error
    if not raw_rows:
        raise ValueError("dataset contains no rows")
    header = [value.strip() for value in raw_rows[0]]
    return header, [list(row) for row in raw_rows[1:]]


def read_dataset_rows(
    path: Path, expected_sheet: str
) -> tuple[list[str], list[list[object | None]]]:
    """Read supported dataset rows through the audited AGM-021 boundary."""

    if path.suffix.lower() == ".xlsx":
        return _xlsx_rows(path, expected_sheet)
    if path.suffix.lower() == ".csv":
        return _csv_rows(path)
    raise ValueError("supported dataset formats are .csv and .xlsx")


def _missing(value: object | None) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value: object | None) -> float | None:
    if _missing(value) or isinstance(value, bool):
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _duplicate_extras(rows: list[list[object | None]], indices: list[int]) -> int:
    counts = Counter(tuple(row[index] for index in indices) for row in rows)
    return sum(count - 1 for count in counts.values() if count > 1)


def audit_dataset(
    contract: FeatureContract,
    dataset_path: Path,
    *,
    expected_sha256: str | None = None,
) -> AuditReport:
    """Audit a dataset without mutating it or performing preprocessing."""

    fingerprint = _sha256(dataset_path)
    expected = (expected_sha256 or contract.dataset_sha256).upper()
    columns, rows = read_dataset_rows(dataset_path, contract.sheet_name)
    if len(columns) != len(set(columns)):
        raise ValueError("dataset contains duplicate column names")
    indices = {column: index for index, column in enumerate(columns)}
    missing_columns = tuple(column for column in contract.required_columns if column not in indices)
    unexpected = tuple(column for column in columns if column not in contract.allowed_columns)
    missing_counts = {
        column: sum(_missing(row[index]) for row in rows) for column, index in indices.items()
    }
    type_counts = {feature.canonical_name: 0 for feature in contract.ordered_features}
    range_counts = {feature.canonical_name: 0 for feature in contract.ordered_features}
    target_counts: Counter[str] = Counter()
    invalid_target = 0
    invalid_rows: set[int] = set()
    numeric_values: dict[str, list[float]] = {
        feature.dataset_column: [] for feature in contract.ordered_features
    }
    for row_number, row in enumerate(rows):
        for feature in contract.ordered_features:
            if feature.dataset_column not in indices:
                continue
            value = row[indices[feature.dataset_column]]
            number = _number(value)
            if _missing(value):
                invalid_rows.add(row_number)
            elif number is None:
                type_counts[feature.canonical_name] += 1
                invalid_rows.add(row_number)
            else:
                numeric_values[feature.dataset_column].append(number)
                if (feature.minimum is not None and number < feature.minimum) or (
                    feature.maximum is not None and number > feature.maximum
                ):
                    range_counts[feature.canonical_name] += 1
                    invalid_rows.add(row_number)
        if contract.target_column not in indices:
            continue
        target = row[indices[contract.target_column]]
        number = _number(target)
        if _missing(target):
            target_counts["missing"] += 1
            invalid_target += 1
            invalid_rows.add(row_number)
        elif number is None or not number.is_integer() or int(number) not in contract.target_values:
            target_counts["invalid"] += 1
            invalid_target += 1
            invalid_rows.add(row_number)
        else:
            target_counts[str(int(number))] += 1
    labeled = sum(target_counts[str(value)] for value in sorted(contract.target_values))
    proportions = {
        str(value): (target_counts[str(value)] / labeled if labeled else 0.0)
        for value in sorted(contract.target_values)
    }
    stats = {
        column: NumericStats(
            min(values), max(values), statistics.fmean(values), statistics.median(values)
        )
        for column, values in numeric_values.items()
        if values
    }
    all_indices = list(range(len(columns)))
    without_time = [index for index, column in enumerate(columns) if column != "Time"]
    feature_target = [
        indices[column]
        for column in (
            *(feature.dataset_column for feature in contract.ordered_features),
            contract.target_column,
        )
        if column in indices
    ]
    leakage = tuple(
        column
        for column in columns
        if column in contract.excluded_columns
        and contract.excluded_columns[column].classification == "known_leakage"
    )
    return AuditReport(
        contract_version=contract.version,
        dataset_sha256=fingerprint,
        row_count=len(rows),
        column_count=len(columns),
        columns=tuple(columns),
        missing_counts=missing_counts,
        invalid_training_rows=len(invalid_rows),
        invalid_type_counts=type_counts,
        invalid_range_counts=range_counts,
        invalid_target_count=invalid_target,
        target_counts=dict(sorted(target_counts.items())),
        target_proportions=proportions,
        exact_duplicate_rows=_duplicate_extras(rows, all_indices),
        duplicates_without_time=_duplicate_extras(rows, without_time),
        feature_target_duplicate_rows=_duplicate_extras(rows, feature_target),
        numeric_ranges=stats,
        known_leakage_columns=leakage,
        missing_required_columns=missing_columns,
        unexpected_columns=unexpected,
        fingerprint_matches=fingerprint == expected,
        structurally_valid=not missing_columns and not unexpected and fingerprint == expected,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    arguments = parser.parse_args(argv)
    try:
        contract = load_contract(arguments.contract)
        report = audit_dataset(
            contract,
            arguments.dataset,
            expected_sha256=arguments.expected_sha256,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.structurally_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
