import json
from pathlib import Path

import pytest

from agrimind_irrigation.contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data_contracts" / "feature-contract-v1.json"


def test_v1_contract_has_exact_approved_order_mapping_and_target() -> None:
    contract = load_contract(CONTRACT)

    assert contract.version == "v1"
    # pragma: allowlist nextline secret
    expected_sha256 = "F776F34FC9C7BE1EEF59614DC41DDEADEF6FDE9DC11D908C4EC8A513D6AF4D2D"
    assert contract.dataset_sha256 == expected_sha256
    assert tuple(feature.canonical_name for feature in contract.ordered_features) == (
        "soil_moisture_index_0_100",
        "air_temperature_c",
        "air_relative_humidity_percent",
    )
    assert tuple(feature.dataset_column for feature in contract.ordered_features) == (
        "Soil Moisture",
        "Temperature",
        "Humidity",
    )
    assert tuple(feature.runtime_source for feature in contract.ordered_features) == (
        "SensorSnapshot.soil_humidity",
        "SensorSnapshot.temperature",
        "SensorSnapshot.air_humidity",
    )
    assert tuple(feature.unit for feature in contract.ordered_features) == (
        "normalized_index_0_100",
        "celsius",
        "percent_relative_humidity",
    )
    assert contract.target_name == "irrigation_required"
    assert contract.target_column == "irrigation"
    assert contract.target_values == frozenset({0, 1})
    assert contract.excluded_columns["best time"].classification == "known_leakage"
    assert contract.excluded_columns["best time"].reason.startswith("Explicitly forbidden")


def test_contract_version_mismatch_is_rejected(tmp_path: Path) -> None:
    content = json.loads(CONTRACT.read_text(encoding="utf-8"))
    content["contract_version"] = "v2"
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(ValueError, match="contract_version must be v1"):
        load_contract(path)


def test_target_encoding_mismatch_is_rejected(tmp_path: Path) -> None:
    content = json.loads(CONTRACT.read_text(encoding="utf-8"))
    content["target"]["encoding"] = {"0": True, "1": False}
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(ValueError, match="0=false and 1=true"):
        load_contract(path)
