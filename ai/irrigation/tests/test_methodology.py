from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from agrimind_irrigation.contract import load_contract
from agrimind_irrigation.methodology import (
    DEFAULT_RANDOM_SEED,
    DatasetValidationError,
    MethodologyError,
    SplitValidationError,
    dataset_diagnostics,
    load_methodology,
    prepare_dataset,
    split_dataset,
    split_summary,
    validate_model_feature_names,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SOURCE = ROOT / "data_contracts" / "feature-contract-v1.json"
METHODOLOGY_SOURCE = ROOT / "methodologies" / "baseline-v1.json"
HEADERS = (
    "Time",
    "crop type",
    "Temperature",
    "Humidity",
    "Soil Moisture",
    "Soil Tempertuer",
    "irrigation",
    "best time",
)

# TEST FIXTURE - NOT REAL AGRICULTURAL DATA.


def excel_serial(value: datetime) -> float:
    return (value - datetime(1899, 12, 30)).total_seconds() / 86400


def write_dataset(path: Path, rows: list[list[object]]) -> str:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def configured_boundaries(tmp_path: Path, digest: str) -> tuple[Path, Path]:
    contract = json.loads(CONTRACT_SOURCE.read_text(encoding="utf-8"))
    contract["dataset"]["primary_file_sha256"] = digest
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    methodology = json.loads(METHODOLOGY_SOURCE.read_text(encoding="utf-8"))
    methodology["dataset_sha256"] = digest
    methodology_path = tmp_path / "methodology.json"
    methodology_path.write_text(json.dumps(methodology), encoding="utf-8")
    return contract_path, methodology_path


def valid_row(when: datetime, target: int, *, moisture: int = 40) -> list[object]:
    return [excel_serial(when), 1, 20, 60, moisture, 18, target, 0]


def test_methodology_and_feature_order_are_exact() -> None:
    methodology = load_methodology(METHODOLOGY_SOURCE)

    assert methodology.version == "baseline-v1"
    assert methodology.random_seed == DEFAULT_RANDOM_SEED == 42
    validate_model_feature_names(
        (
            "soil_moisture_index_0_100",
            "air_temperature_c",
            "air_relative_humidity_percent",
        )
    )
    with pytest.raises(MethodologyError, match="forbidden"):
        validate_model_feature_names(("Time", "air_temperature_c", "best time"))
    with pytest.raises(MethodologyError, match="exact"):
        validate_model_feature_names(
            (
                "air_temperature_c",
                "soil_moisture_index_0_100",
                "air_relative_humidity_percent",
            )
        )
    with pytest.raises(MethodologyError, match="exact"):
        validate_model_feature_names(("soil_moisture_index_0_100",))


def test_preparation_drops_each_invalid_row_once_and_does_not_mutate_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fixture.csv"
    rows = [
        valid_row(datetime(2023, 1, 5, 3), 1, moisture=20),
        valid_row(datetime(2023, 1, 3, 3), 0, moisture=60),
        valid_row(datetime(2023, 1, 4, 3), 1, moisture=30),
        [excel_serial(datetime(2023, 1, 2, 3)), 1, 20, "", "", 18, 0, 0],
    ]
    digest = write_dataset(path, rows)
    before = path.read_bytes()
    contract_path, methodology_path = configured_boundaries(tmp_path, digest)

    prepared = prepare_dataset(
        load_contract(contract_path),
        load_methodology(methodology_path),
        path,
        expected_sha256=digest,
    )

    assert len(prepared.rows) == 3
    assert len(prepared.invalid_rows) == 1
    assert prepared.invalid_rows[0].reasons == (
        "invalid_or_missing:Soil Moisture",
        "invalid_or_missing:Humidity",
    )
    assert [row.observed_at for row in prepared.rows] == sorted(
        row.observed_at for row in prepared.rows
    )
    assert all(row.observed_at.tzinfo is None for row in prepared.rows)
    assert path.read_bytes() == before


def test_fingerprint_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    digest = write_dataset(
        path,
        [
            valid_row(datetime(2023, 1, 3), 0),
            valid_row(datetime(2023, 1, 4), 1),
            valid_row(datetime(2023, 1, 5), 0),
        ],
    )
    contract_path, methodology_path = configured_boundaries(tmp_path, digest)

    with pytest.raises(DatasetValidationError, match="expected fingerprint"):
        prepare_dataset(
            load_contract(contract_path),
            load_methodology(methodology_path),
            path,
            expected_sha256="0" * 64,
        )


def test_excel_1900_conversion_handles_the_historical_leap_year_bug(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    rows = [
        [1, 1, 20, 60, 40, 18, 0, 0],
        [61, 1, 20, 60, 40, 18, 1, 0],
    ]
    digest = write_dataset(path, rows)
    contract_path, methodology_path = configured_boundaries(tmp_path, digest)

    prepared = prepare_dataset(
        load_contract(contract_path),
        load_methodology(methodology_path),
        path,
        expected_sha256=digest,
    )

    assert prepared.rows[0].observed_at == datetime(1900, 1, 1)
    assert prepared.rows[1].observed_at == datetime(1900, 3, 1)


def test_calendar_split_and_conflict_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    rows = [
        valid_row(datetime(2023, 1, 3, 0), 0, moisture=40),
        valid_row(datetime(2023, 1, 3, 1), 1, moisture=20),
        valid_row(datetime(2023, 1, 4, 0), 0, moisture=40),
        valid_row(datetime(2023, 1, 4, 1), 1, moisture=30),
        valid_row(datetime(2023, 1, 5, 0), 1, moisture=40),
        valid_row(datetime(2023, 1, 5, 1), 0, moisture=50),
    ]
    digest = write_dataset(path, rows)
    contract_path, methodology_path = configured_boundaries(tmp_path, digest)
    methodology = load_methodology(methodology_path)
    prepared = prepare_dataset(
        load_contract(contract_path), methodology, path, expected_sha256=digest
    )

    split = split_dataset(prepared, methodology)
    assert [len(split.train), len(split.validation), len(split.test)] == [2, 2, 2]
    assert split.train[-1].observed_at < split.validation[0].observed_at
    assert split.validation[-1].observed_at < split.test[0].observed_at
    assert sum(part["rows"] for part in split_summary(split).values()) == len(prepared.rows)
    diagnostics = dataset_diagnostics(prepared, split)
    assert diagnostics["feature_only"]["conflicting_label_vectors"] == 1
    assert diagnostics["feature_only"]["conflicting_label_rows"] == 3
    assert diagnostics["feature_only_overlap"]["train_validation"]["unique_vectors"] == 1
    assert diagnostics["feature_only_overlap"]["train_test"]["unique_vectors"] == 1


def test_split_rejects_partition_without_both_classes(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    rows = [
        valid_row(datetime(2023, 1, 3, 0), 0),
        valid_row(datetime(2023, 1, 3, 1), 0),
        valid_row(datetime(2023, 1, 4, 0), 0),
        valid_row(datetime(2023, 1, 4, 1), 1),
        valid_row(datetime(2023, 1, 5, 0), 0),
        valid_row(datetime(2023, 1, 5, 1), 1),
    ]
    digest = write_dataset(path, rows)
    contract_path, methodology_path = configured_boundaries(tmp_path, digest)
    methodology = load_methodology(methodology_path)
    prepared = prepare_dataset(
        load_contract(contract_path), methodology, path, expected_sha256=digest
    )

    with pytest.raises(SplitValidationError, match="train must contain both"):
        split_dataset(prepared, methodology)
