"""Deterministic, replayable, related-group-aware splitting."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from agrimind_cv.config import SplitConfig
from agrimind_cv.contracts import SPLIT_CONTRACT_VERSION, Partition, Sample


class SplitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SplitResult:
    assignments: dict[str, Partition]
    group_assignments: dict[str, Partition]
    counts: dict[str, int]
    class_counts: dict[str, dict[str, int]]
    fingerprint: str


def deterministic_group_split(samples: tuple[Sample, ...], config: SplitConfig) -> SplitResult:
    eligible = tuple(
        sorted(
            (sample for sample in samples if not sample.quarantined), key=lambda s: s.relative_path
        )
    )
    if not eligible:
        raise SplitError("cannot split an empty eligible dataset")
    if any(not sample.related_group_id for sample in eligible):
        raise SplitError("every eligible sample requires a related group identifier")
    groups: dict[str, list[Sample]] = defaultdict(list)
    seen_paths: set[str] = set()
    for sample in eligible:
        if sample.relative_path in seen_paths:
            raise SplitError("a sample occurs more than once")
        seen_paths.add(sample.relative_path)
        groups[sample.related_group_id].append(sample)
    if len(groups) < 3:
        raise SplitError("at least three independent groups are required")
    by_label: dict[str, list[str]] = defaultdict(list)
    for group_id, members in groups.items():
        labels = {member.canonical_label.value for member in members}
        if len(labels) != 1:
            raise SplitError("a related group spans binary labels")
        by_label[labels.pop()].append(group_id)

    group_assignments: dict[str, Partition] = {}
    thresholds = (config.train, config.train + config.validation)
    for label in sorted(by_label):
        ranked = sorted(
            by_label[label],
            key=lambda group: (
                hashlib.sha256(f"{config.seed}:{group}".encode()).hexdigest(),
                group,
            ),
        )
        total_samples = sum(len(groups[group]) for group in ranked)
        cumulative = 0
        for group in ranked:
            midpoint = (cumulative + len(groups[group]) / 2) / total_samples
            partition = (
                Partition.TRAIN
                if midpoint <= thresholds[0]
                else Partition.VALIDATION
                if midpoint <= thresholds[1]
                else Partition.TEST
            )
            group_assignments[group] = partition
            cumulative += len(groups[group])
    assignments = {
        sample.relative_path: group_assignments[sample.related_group_id] for sample in eligible
    }
    if set(assignments.values()) != set(Partition):
        raise SplitError("ratios and group count produced an empty partition")
    class_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for sample in eligible:
        class_counts[assignments[sample.relative_path].value][sample.canonical_label.value] += 1
    by_path = {sample.relative_path: sample for sample in eligible}
    canonical = [
        f"version={SPLIT_CONTRACT_VERSION}",
        f"seed={config.seed}",
        f"ratios={config.train:.12g},{config.validation:.12g},{config.test:.12g}",
        *[
            f"{path}\0{by_path[path].related_group_id}\0{assignments[path].value}"
            for path in sorted(assignments)
        ],
    ]
    return SplitResult(
        assignments,
        dict(sorted(group_assignments.items())),
        dict(sorted(Counter(value.value for value in assignments.values()).items())),
        {key: dict(sorted(value.items())) for key, value in sorted(class_counts.items())},
        hashlib.sha256("\n".join(canonical).encode()).hexdigest(),
    )


def assert_no_candidate_leakage(
    samples: tuple[Sample, ...],
    candidates: tuple[tuple[str, str], ...],
    split: SplitResult,
) -> None:
    eligible = {sample.relative_path for sample in samples if not sample.quarantined}
    leaking = [
        pair
        for pair in candidates
        if pair[0] in eligible
        and pair[1] in eligible
        and split.assignments[pair[0]] != split.assignments[pair[1]]
    ]
    if leaking:
        raise SplitError(f"{len(leaking)} eligible near-duplicate pairs cross partitions")


def split_manifest_records(
    samples: tuple[Sample, ...], split: SplitResult
) -> list[dict[str, object]]:
    eligible = {sample.relative_path: sample for sample in samples if not sample.quarantined}
    if set(eligible) != set(split.assignments):
        raise SplitError("split assignments do not exactly match eligible samples")
    return [
        {
            "schema_version": 1,
            "contract_version": SPLIT_CONTRACT_VERSION,
            "split_fingerprint": split.fingerprint,
            "relative_path": path,
            "related_group_id": eligible[path].related_group_id,
            "binary_label": eligible[path].canonical_label.value,
            "partition": split.assignments[path].value,
        }
        for path in sorted(eligible)
    ]


def write_split_manifest(
    samples: tuple[Sample, ...], split: SplitResult, destination: Path
) -> None:
    if destination.exists():
        raise SplitError("split manifest already exists; refusing to overwrite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in split_manifest_records(samples, split)
        ),
        encoding="utf-8",
    )


def replay_split_manifest(
    samples: tuple[Sample, ...], path: Path, config: SplitConfig
) -> SplitResult:
    try:
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, json.JSONDecodeError) as error:
        raise SplitError("split manifest is unreadable") from error
    expected = deterministic_group_split(samples, config)
    if records != split_manifest_records(samples, expected):
        raise SplitError("split manifest does not match deterministic replay")
    return expected
