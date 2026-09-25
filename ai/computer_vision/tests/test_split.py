import json
from dataclasses import replace
from pathlib import Path

import pytest

from agrimind_cv.config import SplitConfig
from agrimind_cv.contracts import CanonicalLabel, Partition, Sample
from agrimind_cv.split import (
    SplitError,
    assert_no_candidate_leakage,
    deterministic_group_split,
    replay_split_manifest,
    split_manifest_records,
    write_split_manifest,
)


def sample(number: int, group: str | None = None, *, quarantined: bool = False) -> Sample:
    label = CanonicalLabel.NORMAL if number % 2 == 0 else CanonicalLabel.ANOMALY
    return Sample(
        f"image-{number}.png",
        "healthy" if label == CanonicalLabel.NORMAL else "anomaly",
        label,
        f"{number:064x}",
        f"{number:016x}",
        12,
        10,
        3,
        group or f"related-{number}",
        quarantined,
        "cross_label_near_duplicate_candidate" if quarantined else None,
    )


def fixture_samples() -> tuple[Sample, ...]:
    return tuple(sample(index) for index in range(40))


def test_same_seed_and_source_reordering_produce_identical_split() -> None:
    samples = fixture_samples()
    config = SplitConfig(0.6, 0.2, 0.2, 42)
    assert deterministic_group_split(samples, config) == deterministic_group_split(
        tuple(reversed(samples)), config
    )


def test_related_group_is_indivisible_and_labels_are_represented() -> None:
    samples = list(fixture_samples())
    samples[2] = sample(2, "same-normal-group")
    samples[4] = sample(4, "same-normal-group")
    result = deterministic_group_split(tuple(samples), SplitConfig(0.6, 0.2, 0.2, 42))
    assert result.assignments["image-2.png"] == result.assignments["image-4.png"]
    for partition in Partition:
        assert set(result.class_counts[partition.value]) == {"NORMAL", "ANOMALY"}


def test_quarantined_sample_never_enters_a_partition() -> None:
    samples = (*fixture_samples(), sample(100, quarantined=True))
    result = deterministic_group_split(samples, SplitConfig(0.6, 0.2, 0.2, 42))
    assert "image-100.png" not in result.assignments


def test_missing_or_mixed_related_group_fails_closed() -> None:
    missing = list(fixture_samples())
    missing[0] = replace(missing[0], related_group_id="")
    with pytest.raises(SplitError, match="group identifier"):
        deterministic_group_split(tuple(missing), SplitConfig(0.6, 0.2, 0.2, 42))
    mixed = list(fixture_samples())
    mixed[0] = sample(0, "mixed")
    mixed[1] = sample(1, "mixed")
    with pytest.raises(SplitError, match="spans binary labels"):
        deterministic_group_split(tuple(mixed), SplitConfig(0.6, 0.2, 0.2, 42))


def test_manifest_round_trip_and_fingerprint_are_repeatable(tmp_path: Path) -> None:
    samples = fixture_samples()
    config = SplitConfig(0.6, 0.2, 0.2, 42)
    split = deterministic_group_split(samples, config)
    path = tmp_path / "split.jsonl"
    write_split_manifest(samples, split, path)
    assert replay_split_manifest(samples, path, config) == split
    assert split_manifest_records(samples, split) == [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_modified_manifest_fails_replay(tmp_path: Path) -> None:
    samples = fixture_samples()
    config = SplitConfig(0.6, 0.2, 0.2, 42)
    split = deterministic_group_split(samples, config)
    path = tmp_path / "split.jsonl"
    write_split_manifest(samples, split, path)
    path.write_text(path.read_text().replace("TRAIN", "TEST", 1), encoding="utf-8")
    with pytest.raises(SplitError, match="does not match"):
        replay_split_manifest(samples, path, config)


def test_remaining_near_duplicate_cross_split_fails() -> None:
    samples = fixture_samples()
    split = deterministic_group_split(samples, SplitConfig(0.6, 0.2, 0.2, 42))
    opposite = next(
        right
        for right in samples[1:]
        if split.assignments[right.relative_path] != split.assignments[samples[0].relative_path]
    )
    with pytest.raises(SplitError, match="cross partitions"):
        assert_no_candidate_leakage(
            samples,
            ((samples[0].relative_path, opposite.relative_path),),
            split,
        )


@pytest.mark.parametrize("ratios", [(0.8, 0.2, 0.2), (1.0, 0.0, 0.0), (-0.1, 0.6, 0.5)])
def test_invalid_ratios_fail(ratios: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError):
        SplitConfig(*ratios, seed=1)
