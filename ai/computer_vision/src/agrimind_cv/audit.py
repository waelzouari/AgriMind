"""Immutable image dataset inspection."""

from __future__ import annotations

import csv
import hashlib
import logging
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from agrimind_cv.config import DatasetConfig
from agrimind_cv.contracts import Sample
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
    samples: tuple[Sample, ...]
    problems: tuple[AuditProblem, ...]
    exact_duplicate_groups: tuple[tuple[str, ...], ...]
    near_duplicate_candidates: tuple[tuple[str, str], ...]
    class_counts: dict[str, int]
    fingerprint: str

    @property
    def valid_for_manifest(self) -> bool:
        fatal = {"unreadable_image", "unknown_label", "unsupported_extension", "duplicate_conflict"}
        return not any(problem.code in fatal for problem in self.problems)


def _difference_hash(image: Image.Image) -> str:
    resized = image.convert("L").resize((9, 8))
    pixels = np.asarray(resized, dtype=np.uint8)
    bits = 0
    for row in range(8):
        for column in range(8):
            bits = (bits << 1) | int(pixels[row, column] > pixels[row, column + 1])
    return f"{bits:016x}"


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


class _HashIndex:
    """Small deterministic BK-tree for bounded perceptual-hash lookup."""

    def __init__(self) -> None:
        self.root: _HashNode | None = None

    def matches(self, sample: Sample, radius: int) -> list[Sample]:
        if self.root is None:
            self.root = _HashNode(sample, {})
            return []
        found = self._search(self.root, sample, radius)
        node = self.root
        while True:
            distance = _hamming(sample.perceptual_hash, node.sample.perceptual_hash)
            if distance not in node.children:
                node.children[distance] = _HashNode(sample, {})
                break
            node = node.children[distance]
        return found

    def _search(self, node: _HashNode, sample: Sample, radius: int) -> list[Sample]:
        distance = _hamming(sample.perceptual_hash, node.sample.perceptual_hash)
        found = [node.sample] if distance <= radius else []
        for edge, child in node.children.items():
            if distance - radius <= edge <= distance + radius:
                found.extend(self._search(child, sample, radius))
        return found


@dataclass(slots=True)
class _HashNode:
    sample: Sample
    children: dict[int, _HashNode]


def audit_dataset(
    root: Path, config: DatasetConfig, logger: logging.Logger | None = None
) -> AuditReport:
    validate_provenance(config)
    if not root.is_dir():
        raise DatasetAuditError("dataset root does not exist or is not a directory")
    log = logger or logging.getLogger(__name__)
    samples: list[Sample] = []
    problems: list[AuditProblem] = []
    by_digest: dict[str, list[Sample]] = defaultdict(list)
    candidates: list[Path] = []
    for directory in sorted(
        path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
    ):
        image_files = sorted(path for path in directory.rglob("*") if path.is_file())
        if directory.name not in config.label_mapping:
            for path in image_files:
                if path.suffix.lower() in config.supported_extensions:
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
        candidates.extend(image_files)
    for path in candidates:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() not in config.supported_extensions:
            problems.append(AuditProblem("unsupported_extension", relative, path.suffix.lower()))
            continue
        source_label = path.relative_to(root).parts[0]
        canonical = config.label_mapping.get(source_label)
        if canonical is None:
            problems.append(AuditProblem("unknown_label", relative, source_label))
            continue
        try:
            raw = path.read_bytes()
            with Image.open(path) as opened:
                opened.verify()
            with Image.open(path) as opened:
                rgb = opened.convert("RGB")
                sample = Sample(
                    relative_path=relative,
                    source_label=source_label,
                    canonical_label=canonical,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    perceptual_hash=_difference_hash(rgb),
                    width=rgb.width,
                    height=rgb.height,
                    channels=3,
                )
        except (OSError, UnidentifiedImageError, ValueError):
            problems.append(AuditProblem("unreadable_image", relative, "image decode failed"))
            continue
        samples.append(sample)
        by_digest[sample.sha256].append(sample)
    duplicate_groups: list[tuple[str, ...]] = []
    for group in by_digest.values():
        if len(group) < 2:
            continue
        paths = tuple(sorted(item.relative_path for item in group))
        duplicate_groups.append(paths)
        if len({item.canonical_label for item in group}) > 1:
            problems.append(
                AuditProblem("duplicate_conflict", paths[0], "same bytes have different labels")
            )
        else:
            problems.append(
                AuditProblem("exact_duplicate", paths[0], f"{len(paths)} identical files")
            )
    near: list[tuple[str, str]] = []
    unique = sorted((group[0] for group in by_digest.values()), key=lambda item: item.relative_path)
    index = _HashIndex()
    for sample in unique:
        near.extend(
            (match.relative_path, sample.relative_path) for match in index.matches(sample, 4)
        )
    ordered_samples = tuple(sorted(samples, key=lambda item: item.relative_path))
    payload = "\n".join(
        f"{item.relative_path}\0{item.canonical_label}\0{item.sha256}" for item in ordered_samples
    ).encode()
    counts = Counter(str(item.canonical_label) for item in ordered_samples)
    report = AuditReport(
        dataset_id=config.dataset_id,
        dataset_version=config.dataset_version,
        samples=ordered_samples,
        problems=tuple(sorted(problems, key=lambda item: (item.code, item.relative_path))),
        exact_duplicate_groups=tuple(sorted(duplicate_groups)),
        near_duplicate_candidates=tuple(near),
        class_counts=dict(sorted(counts.items())),
        fingerprint=hashlib.sha256(payload).hexdigest(),
    )
    log.info(
        "cv_dataset_audit_completed",
        extra={
            "event": "cv_dataset_audit_completed",
            "dataset_id": config.dataset_id,
            "sample_count": len(report.samples),
            "problem_count": len(report.problems),
        },
    )
    return report


def report_as_dict(report: AuditReport) -> dict[str, object]:
    return {
        "dataset_id": report.dataset_id,
        "dataset_version": report.dataset_version,
        "sample_count": len(report.samples),
        "class_counts": report.class_counts,
        "problems": [asdict(item) for item in report.problems],
        "exact_duplicate_groups": report.exact_duplicate_groups,
        "near_duplicate_candidates": report.near_duplicate_candidates,
        "dataset_fingerprint": report.fingerprint,
        "valid_for_manifest": report.valid_for_manifest,
    }


def write_manifest_csv(report: AuditReport, destination: Path) -> None:
    """Write the audited sample contract without silently accepting fatal findings."""
    if not report.valid_for_manifest:
        raise DatasetAuditError("cannot write a manifest from an invalid audit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("manifest already exists; refusing to overwrite")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "relative_path",
                "source_label",
                "canonical_label",
                "sha256",
                "perceptual_hash",
                "width",
                "height",
                "channels",
                "group_id",
            ),
        )
        writer.writeheader()
        for sample in report.samples:
            row = asdict(sample)
            row["canonical_label"] = sample.canonical_label.value
            writer.writerow(row)
    temporary.replace(destination)
