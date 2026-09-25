"""One-way official AGM-031 training, freeze, and held-out TEST evaluation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image

from agrimind_cv.artifacts import repository_git_state
from agrimind_cv.audit import audit_dataset, report_as_dict, write_related_manifest
from agrimind_cv.config import DatasetConfig, SplitConfig
from agrimind_cv.contracts import LABEL_MAP_VERSION, Partition, Sample, SourceVerificationStatus
from agrimind_cv.evaluation import (
    FrozenEvaluationEvidence,
    HeldOutTestScores,
    ValidationScores,
    evaluate_frozen_test,
    metrics_at_threshold,
    select_threshold_from_validation,
)
from agrimind_cv.model_loading import (
    load_mobilenet_v2,
    load_runtime_manifest,
    verify_artifact,
)
from agrimind_cv.preprocessing import PreprocessingContract, preprocess_evaluation
from agrimind_cv.provenance import file_digest, verify_source
from agrimind_cv.split import (
    SplitResult,
    assert_no_candidate_leakage,
    deterministic_group_split,
    write_split_manifest,
)
from agrimind_cv.training import (
    PartitionScores,
    TrainingConfig,
    load_training_runtime,
    score_partition,
    train_and_validate,
)

THRESHOLD_RULE = "agrimind-cv-validation-threshold-v1"


@dataclass(frozen=True, slots=True)
class OfficialConfig:
    schema_version: int
    model_version: str
    artifact_filename: str
    release_tag: str
    execution_device: str
    dataset_fingerprint: str
    related_manifest_fingerprint: str
    split_fingerprint: str
    threshold_rule_version: str

    @classmethod
    def load(cls, path: Path) -> OfficialConfig:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {
            "schema_version",
            "model_version",
            "artifact_filename",
            "release_tag",
            "execution_device",
            "dataset_fingerprint",
            "related_manifest_fingerprint",
            "split_fingerprint",
            "threshold_rule_version",
        }:
            raise ValueError("official evaluation configuration fields are incompatible")
        config = cls(**raw)
        if config.schema_version != 1 or config.threshold_rule_version != THRESHOLD_RULE:
            raise ValueError("official evaluation configuration version is incompatible")
        if config.execution_device != "cuda":
            raise ValueError("official AGM-031 evaluation requires the versioned CUDA device")
        for value in (
            config.dataset_fingerprint,
            config.related_manifest_fingerprint,
            config.split_fingerprint,
        ):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("official expected fingerprints must be lowercase SHA-256 values")
        if Path(config.artifact_filename).name != config.artifact_filename:
            raise ValueError("official artifact filename must not contain a path")
        return config


@dataclass(frozen=True, slots=True)
class OfficialPaths:
    dataset_config: Path
    training_config: Path
    official_config: Path
    dataset_root: Path
    source_archive: Path
    audit_report: Path
    related_manifest: Path
    split_manifest: Path
    artifact: Path
    runtime_manifest: Path
    evaluation_report: Path
    test_opening_marker: Path
    runtime_schema: Path
    evaluation_schema: Path
    repository_root: Path


def _write_once(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists; refusing to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def score_fingerprint(scores: PartitionScores, partition: Partition) -> str:
    if not (
        len(scores.relative_paths)
        == len(scores.source_labels)
        == len(scores.expected)
        == len(scores.anomaly_softmax_probabilities)
    ):
        raise ValueError("partition score fields must have equal length")
    lines = ["version=agrimind-cv-partition-scores-v1", f"partition={partition.value}"]
    lines.extend(
        f"{path}\0{label}\0{expected}\0{score.hex()}"
        for path, label, expected, score in zip(
            scores.relative_paths,
            scores.source_labels,
            scores.expected,
            scores.anomaly_softmax_probabilities,
            strict=True,
        )
    )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def assert_no_content_leakage(samples: tuple[Sample, ...], split: SplitResult) -> None:
    partitions_by_sha: dict[str, set[Partition]] = defaultdict(set)
    for sample in samples:
        if not sample.quarantined:
            partitions_by_sha[sample.sha256].add(split.assignments[sample.relative_path])
    if any(len(partitions) != 1 for partitions in partitions_by_sha.values()):
        raise ValueError("an image SHA-256 crosses dataset partitions")


def _error_summary(scores: PartitionScores, threshold: float) -> dict[str, object]:
    predicted = tuple(
        "ANOMALY" if score >= threshold else "NORMAL"
        for score in scores.anomaly_softmax_probabilities
    )
    errors: dict[str, Counter[str]] = defaultdict(Counter)
    for source, expected, actual in zip(
        scores.source_labels, scores.expected, predicted, strict=True
    ):
        if expected != actual:
            errors[source][f"{expected}_AS_{actual}"] += 1
    return {
        "total_errors": sum(sum(values.values()) for values in errors.values()),
        "by_source_label": {
            source: dict(sorted(values.items())) for source, values in sorted(errors.items())
        },
    }


def _validate_json(payload: dict[str, object], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ValueError(
            "generated evidence is incompatible: " + "; ".join(e.message for e in errors)
        )


def _runtime_environment(torch: Any, device_name: str) -> dict[str, object]:
    return {
        "os": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "pillow": importlib.metadata.version("Pillow"),
        "torch": importlib.metadata.version("torch"),
        "torchvision": importlib.metadata.version("torchvision"),
        "cpu": platform.processor() or "unavailable",
        "torch_threads": int(torch.get_num_threads()),
        "torch_interop_threads": int(torch.get_num_interop_threads()),
        "device": device_name,
        "gpu": torch.cuda.get_device_name(0) if device_name == "cuda" else None,
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "deterministic_settings": {
            "torch_deterministic_algorithms": True,
            "cudnn_deterministic": True,
            "cudnn_benchmark": False,
            "data_loader_workers": 0,
        },
    }


def _training_components(
    path: Path,
) -> tuple[dict[str, Any], TrainingConfig, SplitConfig, PreprocessingContract]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    split_raw = raw["split"]
    preprocessing_raw = raw["preprocessing"]
    augmentation = raw["augmentation"]
    training = TrainingConfig(
        schema_version=int(raw["schema_version"]),
        config_version=str(raw["training_config_version"]),
        architecture=str(raw["architecture"]),
        pretrained_weights=(str(raw["pretrained_weights"]) if raw["pretrained_weights"] else None),
        seed=int(raw["seed"]),
        epochs=int(raw["epochs"]),
        batch_size=int(raw["batch_size"]),
        learning_rate=float(raw["learning_rate"]),
        early_stopping_patience=int(raw["early_stopping_patience"]),
        horizontal_flip_probability=float(augmentation["horizontal_flip_probability"]),
        optimizer=str(raw["optimizer"]),
    )
    split = SplitConfig(
        float(split_raw["train"]),
        float(split_raw["validation"]),
        float(split_raw["test"]),
        training.seed,
        int(split_raw["schema_version"]),
        str(split_raw["contract_version"]),
    )
    preprocessing = PreprocessingContract(
        schema_version=int(preprocessing_raw["schema_version"]),
        contract_version=str(preprocessing_raw["contract_version"]),
        width=int(preprocessing_raw["width"]),
        height=int(preprocessing_raw["height"]),
        color_mode=str(preprocessing_raw["color_mode"]),
        dtype=str(preprocessing_raw["dtype"]),
        layout=str(preprocessing_raw["layout"]),
        resize=str(preprocessing_raw["resize"]),
        mean=cast(
            tuple[float, float, float], tuple(float(value) for value in preprocessing_raw["mean"])
        ),
        std=cast(
            tuple[float, float, float], tuple(float(value) for value in preprocessing_raw["std"])
        ),
    )
    return raw, training, split, preprocessing


def run_official_evaluation(paths: OfficialPaths) -> dict[str, object]:
    """Execute the irreversible official pipeline; TEST opens only after freeze."""
    destinations = (
        paths.audit_report,
        paths.related_manifest,
        paths.split_manifest,
        paths.artifact,
        paths.runtime_manifest,
        paths.evaluation_report,
        paths.test_opening_marker,
    )
    if any(path.exists() for path in destinations):
        raise FileExistsError("official output already exists; refusing to rerun or overwrite")
    git = repository_git_state(paths.repository_root)
    if git.dirty:
        raise ValueError("official evaluation must start from a clean Git revision")
    official = OfficialConfig.load(paths.official_config)
    if paths.artifact.name != official.artifact_filename:
        raise ValueError("artifact destination filename does not match official configuration")
    dataset = DatasetConfig.load(paths.dataset_config)
    source = verify_source(paths.dataset_root, dataset, archive=paths.source_archive)
    if source.status != SourceVerificationStatus.VERIFIED:
        raise ValueError("official dataset source is not VERIFIED")
    audit = audit_dataset(paths.dataset_root, dataset, source_evidence=source)
    if not audit.valid_for_manifest:
        raise ValueError("dataset audit failed")
    if audit.dataset_fingerprint != official.dataset_fingerprint:
        raise ValueError("dataset fingerprint differs from approved AGM-030 evidence")
    if audit.related_manifest_fingerprint != official.related_manifest_fingerprint:
        raise ValueError("related-manifest fingerprint differs from approved AGM-030 evidence")
    _write_once(paths.audit_report, report_as_dict(audit))
    write_related_manifest(audit, paths.related_manifest)

    raw_training, training, split_config, preprocessing = _training_components(
        paths.training_config
    )
    torch_raw, _ = load_training_runtime()
    torch = cast(Any, torch_raw)
    if official.execution_device == "cuda" and not torch.cuda.is_available():
        raise ValueError("official CUDA execution device is unavailable")
    split = deterministic_group_split(audit.samples, split_config)
    if split.fingerprint != official.split_fingerprint:
        raise ValueError("split fingerprint differs from approved AGM-030 evidence")
    assert_no_candidate_leakage(audit.samples, audit.near_duplicate_candidates, split)
    assert_no_content_leakage(audit.samples, split)
    write_split_manifest(audit.samples, split, paths.split_manifest)

    outcome = train_and_validate(
        dataset_root=paths.dataset_root,
        samples=audit.eligible_samples,
        split=split,
        config=training,
        preprocessing=preprocessing,
        model_destination=paths.artifact,
        device_name=official.execution_device,
    )
    validation_scores = score_partition(
        dataset_root=paths.dataset_root,
        samples=audit.eligible_samples,
        split=split,
        partition=Partition.VALIDATION,
        config=training,
        preprocessing=preprocessing,
        model_path=paths.artifact,
        device_name=official.execution_device,
    )
    validation_fingerprint = score_fingerprint(validation_scores, Partition.VALIDATION)
    threshold = select_threshold_from_validation(
        ValidationScores(
            validation_scores.expected,
            validation_scores.anomaly_softmax_probabilities,
            validation_fingerprint,
        )
    )
    artifact_sha = file_digest(paths.artifact)
    runtime_manifest: dict[str, object] = {
        "schema_version": 1,
        "model_version": official.model_version,
        "architecture": training.architecture,
        "label_mapping": {"NORMAL": 0, "ANOMALY": 1},
        "preprocessing_version": preprocessing.contract_version,
        "dataset_fingerprint": audit.dataset_fingerprint,
        "split_fingerprint": split.fingerprint,
        "artifact_path": official.artifact_filename,
        "artifact_size_bytes": paths.artifact.stat().st_size,
        "artifact_sha256": artifact_sha,
        "decision_threshold": threshold.threshold,
        "validation_fingerprint": validation_fingerprint,
    }
    pretest_manifest = paths.artifact.with_suffix(".runtime.json")
    _validate_json(runtime_manifest, paths.runtime_schema)
    _write_once(pretest_manifest, runtime_manifest)
    parsed_manifest = load_runtime_manifest(pretest_manifest, paths.runtime_schema)
    verify_artifact(parsed_manifest, paths.artifact)

    frozen = FrozenEvaluationEvidence(
        artifact_sha,
        official.model_version,
        preprocessing.contract_version,
        threshold,
    )
    if (
        not all((frozen.model_frozen, frozen.preprocessing_frozen, frozen.threshold_frozen))
        or threshold.rule_version != official.threshold_rule_version
        or audit.dataset_fingerprint != official.dataset_fingerprint
        or split.fingerprint != official.split_fingerprint
        or LABEL_MAP_VERSION != "agrimind-cv-binary-label-map-v1"
        or not git.revision
    ):
        raise ValueError("held-out TEST opening gate failed")

    paths.test_opening_marker.parent.mkdir(parents=True, exist_ok=True)
    with paths.test_opening_marker.open("x", encoding="utf-8") as marker:
        marker.write(f"opened_at={datetime.now(UTC).isoformat()}\nrevision={git.revision}\n")
    test_started = time.perf_counter()
    test_scores = score_partition(
        dataset_root=paths.dataset_root,
        samples=audit.eligible_samples,
        split=split,
        partition=Partition.TEST,
        config=training,
        preprocessing=preprocessing,
        model_path=paths.artifact,
        device_name=official.execution_device,
    )
    test_report = evaluate_frozen_test(
        HeldOutTestScores(test_scores.expected, test_scores.anomaly_softmax_probabilities), frozen
    )
    test_duration = time.perf_counter() - test_started
    evidence: dict[str, object] = {
        "schema_version": 1,
        "model": {
            "version": official.model_version,
            "architecture": training.architecture,
            "pretrained_weights": training.pretrained_weights,
            "label_mapping": {"NORMAL": 0, "ANOMALY": 1},
            "preprocessing_version": preprocessing.contract_version,
        },
        "artifact": {
            "filename": official.artifact_filename,
            "size_bytes": paths.artifact.stat().st_size,
            "sha256": artifact_sha,
            "distribution": "github_release",
            "release_tag": official.release_tag,
            "release_asset_uploaded": False,
        },
        "dataset": {
            "id": dataset.dataset_id,
            "version": dataset.dataset_version,
            "source_revision": dataset.source_revision,
            "source_archive_sha256": source.archive_sha256,
            "fingerprint": audit.dataset_fingerprint,
            "related_manifest_fingerprint": audit.related_manifest_fingerprint,
        },
        "split": {
            "fingerprint": split.fingerprint,
            "counts": split.counts,
            "class_counts": split.class_counts,
            "leakage_checks": {
                "related_groups_cross_partitions": 0,
                "image_sha_cross_partitions": 0,
                "test_used_for_training": False,
                "test_used_for_threshold_selection": False,
            },
        },
        "training": {
            "configuration": raw_training,
            "outcome": asdict(outcome),
        },
        "validation": {
            "sample_count": len(validation_scores.expected),
            "fingerprint": validation_fingerprint,
            "score_name": "anomaly_softmax_probability",
            "threshold": threshold.threshold,
            "threshold_policy": threshold.rule_version,
            "metrics_at_threshold": asdict(threshold.metrics),
            "metrics_at_default_0_5": asdict(
                metrics_at_threshold(
                    validation_scores.expected,
                    validation_scores.anomaly_softmax_probabilities,
                    0.5,
                )
            ),
            "scoring_duration_seconds": validation_scores.duration_seconds,
        },
        "test": {
            "opened_once_after_freeze": True,
            "sample_count": test_report.sample_count,
            "metrics": asdict(test_report.metrics),
            "roc_auc": test_report.roc_auc,
            "average_precision": test_report.average_precision,
            "evaluation_duration_seconds": test_duration,
            "error_analysis": _error_summary(test_scores, threshold.threshold),
        },
        "execution": {
            "scientific_git_revision": git.revision,
            "git_dirty_at_start": git.dirty,
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "runtime": _runtime_environment(torch, official.execution_device),
        },
        "limitations": [
            "PlantVillage uses predominantly controlled imagery and does not establish "
            "field accuracy.",
            "The anomaly softmax probability is not calibrated.",
            "NORMAL/ANOMALY is visual screening, not disease diagnosis.",
        ],
    }
    _validate_json(evidence, paths.evaluation_schema)
    _write_once(paths.runtime_manifest, runtime_manifest)
    _write_once(paths.evaluation_report, evidence)

    # The same strict, network-free runtime loader used by the service must accept the artifact.
    loaded = load_mobilenet_v2(parsed_manifest, paths.artifact)
    synthetic = preprocess_evaluation(
        Image.new("RGB", (224, 224), color=(127, 127, 127)), preprocessing
    )
    prediction, probability = loaded.predict(torch.from_numpy(synthetic).unsqueeze(0))
    if prediction not in {"NORMAL", "ANOMALY"} or not 0.0 <= probability <= 1.0:
        raise RuntimeError("official artifact smoke inference failed")
    return evidence
