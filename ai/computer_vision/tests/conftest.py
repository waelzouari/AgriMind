from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def dataset_config_file(tmp_path: Path) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset_id": "test-plants",
                "dataset_version": "1",
                "source_url": "https://example.test/dataset",
                "source_revision": "a" * 40,
                "doi": "10.1234/example",
                "authors": ["Test Author"],
                "license": {
                    "id": "CC-BY-4.0",
                    "url": "https://creativecommons.org/licenses/by/4.0/",
                },
                "archive": {"name": "test.zip", "sha256": "0" * 64},
                "label_map_version": "agrimind-cv-binary-label-map-v1",
                "near_duplicate_hamming_threshold": 0,
                "label_mapping": {
                    "healthy": "NORMAL",
                    "anomaly": "ANOMALY",
                },
                "excluded_source_labels": [],
                "supported_extensions": [".png", ".jpg"],
                "grouping_key": "plant_id",
                "known_limitations": ["test fixture only"],
            }
        ),
        encoding="utf-8",
    )
    return path


def make_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (12, 10), color)
    marker = (color[0] * 3 + color[1] * 5 + color[2] * 7) % 11
    for row in range(10):
        image.putpixel((marker, row), (255 - color[0], 255 - color[1], 255 - color[2]))
    image.save(path)
