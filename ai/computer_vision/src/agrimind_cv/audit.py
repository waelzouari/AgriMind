"""Deterministic image audit, quarantine, and related-image grouping."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from agrimind_cv.config import DatasetConfig
from agrimind_cv.contracts import (
    RELATED_MANIFEST_VERSION,
    Sample,
    SourceEvidence,
    SourceVerificationStatus,
)
from agrimind_cv.provenance import validate_provenance


class DatasetAuditError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AuditProblem:
    code: str
    relative_path: str
    detail: str


@dataclass(frozen=True, slots=True)
class AuditReport:
    dataset_id: str
    dataset_version: str
    label_map_version: str
    source_mapping: dict[str, str]
    source_evidence: SourceEvidence
    samples: tuple[Sample, ...]
    problems: tuple[AuditProblem, ...]
    exact_duplicate_groups: tuple[tuple[str, ...], ...]
    near_duplicate_candidates: tuple[tuple[str, str], ...]
    cross_label_candidates: tuple[tuple[str, str], ...]
    class_counts: dict[str, int]
    total_files: int
    accepted_count: int
    eligible_count: int
    excluded_count: int
    invalid_count: int
    quarantined_count: int
    dataset_fingerprint: str
    related_manifest_fingerprint: str

    @property
    def eligible_samples(self) -> tuple[Sample, ...]:
        return tuple(sample for sample in self.samples if not sample.quarantined)

    @property
    def valid_for_manifest(self) -> bool:
        fatal = {"unreadable_image", "unknown_label", "unsupported_extension", "duplicate_conflict"}
        return not any(problem.code in fatal for problem in self.problems)


def _sha(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _difference_hash(image: Image.Image) -> str:
    pixels = np.asarray(image.convert("L").resize((9, 8)), dtype=np.uint8)
    bits = 0
    for row in range(8):
        for column in range(8):
            bits = (bits << 1) | int(pixels[row, column] > pixels[row, column + 1])
    return f"{bits:016x}"


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


class _UnionFind:
    def __init__(self, paths: list[str]) -> None:
        self.parent = {path: path for path in paths}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        first, second = self.find(left), self.find(right)
        if first != second:
            low, high = sorted((first, second))
            self.parent[high] = low


@dataclass(slots=True)
class _HashNode:
    sample: Sample
    children: dict[int, _HashNode]


class _HashIndex:
    """Deterministic BK-tree for bounded 64-bit perceptual-hash lookup."""

    def __init__(self) -> None:
        self.root: _HashNode | None = None

    def add_and_match(self, sample: Sample, radius: int) -> list[Sample]:
        if self.root is None:
            self.root = _HashNode(sample, {})
            return []
        found = self._search(self.root, sample, radius)
        node = self.root
        while True:
            distance = _hamming(sample.perceptual_hash, node.sample.perceptual_hash)
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = _HashNode(sample, {})
                break
            node = child
        return sorted(found, key=lambda item: item.relative_path)

    def _search(self, node: _HashNode, sample: Sample, radius: int) -> list[Sample]:
        distance = _hamming(sample.perceptual_hash, node.sample.perceptual_hash)
        found = [node.sample] if distance <= radius else []
        for edge in sorted(node.children):
            if distance - radius <= edge <= distance + radius:
                found.extend(self._search(node.children[edge], sample, radius))
        return found


def _unverified(config: DatasetConfig) -> SourceEvidence:
    return SourceEvidence(
        1,
        SourceVerificationStatus.UNVERIFIED,
        "not_supplied",
        config.source_url,
        config.source_revision,
        None,
        None,
        None,
        "Audit caller did not supply source evidence",
    )


def audit_dataset(
    root: Path,
    config: DatasetConfig,
    *,
    source_evidence: SourceEvidence | None = None,
) -> AuditReport:
    validate_provenance(config)
    if not root.is_dir():
        raise DatasetAuditError("dataset root does not exist or is not a directory")
    evidence = source_evidence or _unverified(config)
    samples: list[Sample] = []
    problems: list[AuditProblem] = []
    total_files = 0
    for directory in sorted(
        (path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: path.name,
    ):
        files = sorted(
            (path for path in directory.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(root).as_posix(),
        )
        total_files += len(files)
        if directory.name not in config.label_mapping:
            for path in files:
                problems.append(
                    AuditProblem(
                        "excluded_source_label"
                        if directory.name in config.excluded_source_labels
                        else "unknown_label",
                        path.relative_to(root).as_posix(),
                        directory.name,
                    )
                )
            continue
        for path in files:
            relative = path.relative_to(root).as_posix()
            if path.suffix.lower() not in config.supported_extensions:
                problems.append(
                    AuditProblem("unsupported_extension", relative, path.suffix.lower())
                )
                continue
            try:
                raw = path.read_bytes()
                with Image.open(path) as opened:
                    opened.verify()
                with Image.open(path) as opened:
                    rgb = opened.convert("RGB")
                    samples.append(
                        Sample(
                            relative,
                            directory.name,
                            config.label_mapping[directory.name],
                            hashlib.sha256(raw).hexdigest(),
                            _difference_hash(rgb),
                            rgb.width,
                            rgb.height,
                            3,
                        )
                    )
            except (OSError, UnidentifiedImageError, ValueError):
                problems.append(AuditProblem("unreadable_image", relative, "image decode failed"))

    samples.sort(key=lambda sample: sample.relative_path)
    union = _UnionFind([sample.relative_path for sample in samples])
    by_digest: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        by_digest[sample.sha256].append(sample)
    exact_groups: list[tuple[str, ...]] = []
    for group in sorted(by_digest.values(), key=lambda items: items[0].sha256):
        if len(group) < 2:
            continue
        paths = tuple(sorted(item.relative_path for item in group))
        exact_groups.append(paths)
        if len({item.canonical_label for item in group}) > 1:
            problems.append(
                AuditProblem("duplicate_conflict", paths[0], "same bytes have different labels")
            )
        else:
            for duplicate_path in paths[1:]:
                union.union(paths[0], duplicate_path)
            problems.append(
                AuditProblem("exact_duplicate", paths[0], f"{len(paths)} identical files")
            )

    unique = sorted((items[0] for items in by_digest.values()), key=lambda item: item.relative_path)
    near: list[tuple[str, str]] = []
    cross_label: list[tuple[str, str]] = []
    quarantined_paths: set[str] = set()
    index = _HashIndex()
    for right in unique:
        for left in index.add_and_match(right, config.near_duplicate_hamming_threshold):
            pair = (left.relative_path, right.relative_path)
            near.append(pair)
            if left.canonical_label == right.canonical_label:
                union.union(*pair)
            else:
                cross_label.append(pair)
                quarantined_paths.update(pair)

    component_members: dict[str, list[str]] = defaultdict(list)
    for sample in samples:
        component_members[union.find(sample.relative_path)].append(sample.relative_path)
    group_ids = {
        path: "related-" + _sha(sorted(members))[:20]
        for members in component_members.values()
        for path in members
    }
    quarantined_roots = {union.find(path) for path in quarantined_paths}
    quarantined_paths = {
        sample.relative_path
        for sample in samples
        if union.find(sample.relative_path) in quarantined_roots
    }
    related = tuple(
        replace(
            sample,
            related_group_id=group_ids[sample.relative_path],
            quarantined=sample.relative_path in quarantined_paths,
            quarantine_reason=(
                "cross_label_near_duplicate_candidate"
                if sample.relative_path in quarantined_paths
                else None
            ),
        )
        for sample in samples
    )
    mapping_lines = [
        f"{source}\0{config.label_mapping[source].value}" for source in sorted(config.label_mapping)
    ]
    dataset_lines = [
        "contract=agrimind-cv-dataset-fingerprint-v1",
        f"dataset={config.dataset_id}\0{config.dataset_version}",
        f"label_map={config.label_map_version}",
        f"near_duplicate_hamming_threshold={config.near_duplicate_hamming_threshold}",
        "excluded=" + ",".join(sorted(config.excluded_source_labels)),
        "extensions=" + ",".join(sorted(config.supported_extensions)),
        *mapping_lines,
        *[
            "\0".join(
                (
                    sample.relative_path,
                    sample.source_label,
                    sample.canonical_label.value,
                    sample.sha256,
                    sample.perceptual_hash,
                    str(sample.width),
                    str(sample.height),
                    str(sample.channels),
                )
            )
            for sample in related
        ],
    ]
    related_lines = [
        f"version={RELATED_MANIFEST_VERSION}",
        *[
            "\0".join(
                (
                    sample.relative_path,
                    sample.sha256,
                    sample.perceptual_hash,
                    sample.related_group_id,
                    sample.canonical_label.value,
                    str(sample.quarantined).lower(),
                    sample.quarantine_reason or "",
                )
            )
            for sample in related
        ],
    ]
    counts = Counter(sample.canonical_label.value for sample in related if not sample.quarantined)
    invalid = sum(
        problem.code
        in {"unreadable_image", "unknown_label", "unsupported_extension", "duplicate_conflict"}
        for problem in problems
    )
    excluded = sum(problem.code == "excluded_source_label" for problem in problems)
    return AuditReport(
        config.dataset_id,
        config.dataset_version,
        config.label_map_version,
        {key: value.value for key, value in sorted(config.label_mapping.items())},
        evidence,
        related,
        tuple(sorted(problems, key=lambda problem: (problem.relative_path, problem.code))),
        tuple(sorted(exact_groups)),
        tuple(near),
        tuple(cross_label),
        dict(sorted(counts.items())),
        total_files,
        len(related),
        len(related) - len(quarantined_paths),
        excluded,
        invalid,
        len(quarantined_paths),
        _sha(dataset_lines),
        _sha(related_lines),
    )


def related_manifest_records(report: AuditReport) -> list[dict[str, object]]:
    return [
        {
            "schema_version": 1,
            "manifest_version": RELATED_MANIFEST_VERSION,
            "manifest_fingerprint": report.related_manifest_fingerprint,
            "dataset_fingerprint": report.dataset_fingerprint,
            "relative_path": sample.relative_path,
            "sha256": sample.sha256,
            "perceptual_hash": sample.perceptual_hash,
            "related_group_id": sample.related_group_id,
            "binary_label": sample.canonical_label.value,
            "quarantined": sample.quarantined,
            "quarantine_reason": sample.quarantine_reason,
        }
        for sample in report.samples
    ]


def write_related_manifest(report: AuditReport, destination: Path) -> None:
    if destination.exists():
        raise DatasetAuditError("related manifest already exists; refusing to overwrite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n" for record in related_manifest_records(report)
        ),
        encoding="utf-8",
    )


def report_as_dict(report: AuditReport) -> dict[str, object]:
    result = asdict(report)
    result.pop("samples")
    source_evidence = result["source_evidence"]
    if not isinstance(source_evidence, dict):
        raise DatasetAuditError("serialized source evidence must be an object")
    source_evidence["status"] = report.source_evidence.status.value
    return result
