from agrimind_cv.config import SplitConfig
from agrimind_cv.contracts import CanonicalLabel, Sample
from agrimind_cv.split import SplitError, deterministic_group_split


def sample(number: int, group: str | None) -> Sample:
    return Sample(
        relative_path=f"image-{number}.png",
        source_label="healthy" if number % 2 == 0 else "anomaly",
        canonical_label=CanonicalLabel.NORMAL if number % 2 == 0 else CanonicalLabel.ANOMALY,
        sha256=f"{number:064x}",
        perceptual_hash=f"{number:016x}",
        width=12,
        height=10,
        channels=3,
        group_id=group,
    )


def test_split_is_deterministic_and_keeps_groups_together() -> None:
    samples = tuple(sample(index, f"plant-{index // 2}") for index in range(20))
    config = SplitConfig(0.6, 0.2, 0.2, seed=42)
    first = deterministic_group_split(samples, config)
    second = deterministic_group_split(samples, config)
    assert first == second
    for index in range(0, 20, 2):
        assert (
            first.assignments[f"image-{index}.png"] == first.assignments[f"image-{index + 1}.png"]
        )
    assert set(first.counts) == {"train", "validation", "test"}


def test_missing_group_metadata_fails_closed() -> None:
    samples = tuple(sample(index, None) for index in range(6))
    try:
        deterministic_group_split(samples, SplitConfig(0.5, 0.25, 0.25, seed=1))
    except SplitError as error:
        assert "group identifiers" in str(error)
    else:
        raise AssertionError("missing grouping metadata must block splitting")


def test_duplicate_bytes_across_source_groups_block_splitting() -> None:
    samples = list(sample(index, f"plant-{index}") for index in range(6))
    duplicate = samples[1]
    samples[1] = Sample(
        relative_path=duplicate.relative_path,
        source_label=duplicate.source_label,
        canonical_label=duplicate.canonical_label,
        sha256=samples[0].sha256,
        perceptual_hash=duplicate.perceptual_hash,
        width=duplicate.width,
        height=duplicate.height,
        channels=duplicate.channels,
        group_id=duplicate.group_id,
    )
    try:
        deterministic_group_split(tuple(samples), SplitConfig(0.5, 0.25, 0.25, seed=1))
    except SplitError as error:
        assert "duplicate bytes" in str(error)
    else:
        raise AssertionError("cross-group duplicate must block splitting")


def test_unGrouped_profile_stratifies_and_keeps_exact_duplicates_together() -> None:
    samples = [sample(index, None) for index in range(20)]
    duplicate = samples[0]
    samples.append(
        Sample(
            "copy.png",
            duplicate.source_label,
            duplicate.canonical_label,
            duplicate.sha256,
            duplicate.perceptual_hash,
            duplicate.width,
            duplicate.height,
            duplicate.channels,
        )
    )
    result = deterministic_group_split(
        tuple(samples), SplitConfig(0.6, 0.2, 0.2, seed=42, require_group_ids=False)
    )
    assert result.assignments[duplicate.relative_path] == result.assignments["copy.png"]
    for partition in ("train", "validation", "test"):
        assert set(result.class_counts[partition]) == {"NORMAL", "ANOMALY"}
