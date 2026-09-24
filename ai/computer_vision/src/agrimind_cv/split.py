"""Deterministic, group-aware dataset splitting."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from agrimind_cv.config import SplitConfig
from agrimind_cv.contracts import Sample


class SplitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SplitResult:
    assignments: dict[str, str]
    counts: dict[str, int]
    class_counts: dict[str, dict[str, int]]
    fingerprint: str


def deterministic_group_split(samples: tuple[Sample, ...], config: SplitConfig) -> SplitResult:
    if not samples:
        raise SplitError("cannot split an empty dataset")
    if config.require_group_ids and any(sample.group_id is None for sample in samples):
        raise SplitError("scientifically safe splitting requires source group identifiers")
    digest_groups: dict[str, set[str | None]] = defaultdict(set)
    for sample in samples:
        digest_groups[sample.sha256].add(sample.group_id)
    if any(len(group_ids) > 1 for group_ids in digest_groups.values()):
        raise SplitError("exact duplicate bytes span multiple source groups")
    groups: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        group = sample.group_id or sample.sha256
        groups[group].append(sample)
    if len(groups) < 3:
        raise SplitError("at least three independent groups are required")
    thresholds = (config.train, config.train + config.validation)
    assignments: dict[str, str] = {}
    groups_by_label: dict[str, list[str]] = defaultdict(list)
    for group, members in groups.items():
        composition = Counter(member.canonical_label.value for member in members)
        signature = "|".join(f"{label}:{composition[label]}" for label in sorted(composition))
        groups_by_label[signature].append(group)
    for label_groups in groups_by_label.values():
        ranked = sorted(
            label_groups,
            key=lambda group: hashlib.sha256(f"{config.seed}:{group}".encode()).hexdigest(),
        )
        total = len(ranked)
        for index, group in enumerate(ranked):
            fraction = (index + 0.5) / total
            split = (
                "train"
                if fraction <= thresholds[0]
                else "validation"
                if fraction <= thresholds[1]
                else "test"
            )
            for sample in groups[group]:
                assignments[sample.relative_path] = split
    if set(assignments.values()) != {"train", "validation", "test"}:
        raise SplitError("ratios and group count produced an empty split")
    split_counts = Counter(assignments.values())
    class_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for sample in samples:
        class_counts[assignments[sample.relative_path]][str(sample.canonical_label)] += 1
    canonical = "\n".join(f"{path}\0{assignments[path]}" for path in sorted(assignments))
    return SplitResult(
        assignments=assignments,
        counts=dict(sorted(split_counts.items())),
        class_counts={
            key: dict(sorted(value.items())) for key, value in sorted(class_counts.items())
        },
        fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
    )
