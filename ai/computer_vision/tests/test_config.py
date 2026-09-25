import json
from pathlib import Path

import pytest

from agrimind_cv.config import ConfigurationError, DatasetConfig, SplitConfig


def test_dataset_configuration_loads_verified_binary_mapping(dataset_config_file: Path) -> None:
    config = DatasetConfig.load(dataset_config_file)
    assert config.dataset_id == "test-plants"
    assert set(config.label_mapping.values()) == {"NORMAL", "ANOMALY"}


def test_plantvillage_mapping_is_explicit_and_binary() -> None:
    config_path = (
        Path(__file__).parents[1] / "configs" / "datasets" / "plantvillage-notebook-mirror-v1.json"
    )
    config = DatasetConfig.load(config_path)
    assert len(config.label_mapping) == 38
    assert config.label_mapping["Apple___healthy"].value == "NORMAL"
    assert config.label_mapping["Tomato___Late_blight"].value == "ANOMALY"
    assert "x_Removed_from_Healthy_leaves" not in config.label_mapping
    assert config.excluded_source_labels == {"x_Removed_from_Healthy_leaves"}
    assert config.grouping_key is None
    assert config.label_map_version == "agrimind-cv-binary-label-map-v1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label_map_version", "unknown"),
        ("near_duplicate_hamming_threshold", -1),
        ("near_duplicate_hamming_threshold", 65),
    ],
)
def test_unsupported_dataset_contract_values_fail(
    tmp_path: Path, dataset_config_file: Path, field: str, value: object
) -> None:
    raw = json.loads(dataset_config_file.read_text(encoding="utf-8"))
    raw[field] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        DatasetConfig.load(path)


def test_missing_field_unknown_field_and_invalid_label_fail(
    tmp_path: Path, dataset_config_file: Path
) -> None:
    raw = json.loads(dataset_config_file.read_text(encoding="utf-8"))
    raw.pop("authors")
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="fields"):
        DatasetConfig.load(path)
    raw = json.loads(dataset_config_file.read_text(encoding="utf-8"))
    raw["unexpected"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="fields"):
        DatasetConfig.load(path)
    raw.pop("unexpected")
    raw["label_mapping"]["healthy"] = "DISEASE"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="unsupported target"):
        DatasetConfig.load(path)


@pytest.mark.parametrize("ratios", [(0.8, 0.2, 0.2), (1.0, 0.0, 0.0), (-0.1, 0.6, 0.5)])
def test_invalid_split_ratios_are_rejected(ratios: tuple[float, float, float]) -> None:
    with pytest.raises(ConfigurationError):
        SplitConfig(*ratios, seed=1)
