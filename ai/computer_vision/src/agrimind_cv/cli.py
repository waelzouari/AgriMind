"""CLI for verifiable audit and validation-only AGM-030 training."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agrimind_cv.artifacts import ArtifactMetadata, repository_git_state, write_metadata
from agrimind_cv.audit import audit_dataset, report_as_dict, write_related_manifest
from agrimind_cv.baseline import (
    BASELINE_PREPROCESSING_VERSION,
    train_mean_rgb_centroid_baseline,
    write_baseline_artifact,
)
from agrimind_cv.config import DatasetConfig, SplitConfig
from agrimind_cv.contracts import LABEL_MAP_VERSION, SourceVerificationStatus
from agrimind_cv.official_evaluation import OfficialPaths, run_official_evaluation
from agrimind_cv.preprocessing import PreprocessingContract
from agrimind_cv.provenance import file_digest, verify_source
from agrimind_cv.selection import BASELINE_ID, select_model
from agrimind_cv.split import (
    assert_no_candidate_leakage,
    deterministic_group_split,
    write_split_manifest,
)
from agrimind_cv.training import TrainingConfig, load_training_runtime, train_and_validate

ROOT = Path(__file__).resolve().parents[4]
SCHEMA = ROOT / "ai/computer_vision/data_contracts/artifact-metadata.v2.schema.json"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="agrimind-cv")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("audit", "train"):
        command = commands.add_parser(name)
        command.add_argument("--dataset-config", type=Path, required=True)
        command.add_argument("--dataset-root", type=Path, required=True)
        command.add_argument("--source-archive", type=Path)
        command.add_argument("--source-evidence", type=Path)
        command.add_argument("--audit-report", type=Path, required=True)
        command.add_argument("--related-manifest", type=Path, required=True)
    train = commands.choices["train"]
    train.add_argument("--training-config", type=Path, required=True)
    train.add_argument("--split-manifest", type=Path, required=True)
    train.add_argument("--model", type=Path, required=True)
    train.add_argument("--metadata", type=Path, required=True)
    train.add_argument("--artifact-id", required=True)
    train.add_argument("--artifact-version", required=True)
    official = commands.add_parser("official-evaluate")
    official.add_argument("--dataset-config", type=Path, required=True)
    official.add_argument("--training-config", type=Path, required=True)
    official.add_argument("--official-config", type=Path, required=True)
    official.add_argument("--dataset-root", type=Path, required=True)
    official.add_argument("--source-archive", type=Path, required=True)
    official.add_argument("--audit-report", type=Path, required=True)
    official.add_argument("--related-manifest", type=Path, required=True)
    official.add_argument("--split-manifest", type=Path, required=True)
    official.add_argument("--model", type=Path, required=True)
    official.add_argument("--runtime-manifest", type=Path, required=True)
    official.add_argument("--evaluation-report", type=Path, required=True)
    official.add_argument("--test-opening-marker", type=Path, required=True)
    return result


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return {str(key): item for key, item in value.items()}


def _training_components(
    path: Path,
) -> tuple[dict[str, Any], TrainingConfig, SplitConfig, PreprocessingContract]:
    raw = _object(json.loads(path.read_text(encoding="utf-8")), "training config")
    required = {
        "schema_version",
        "training_config_version",
        "architecture",
        "pretrained_weights",
        "seed",
        "split",
        "preprocessing",
        "augmentation",
        "selection",
        "optimizer",
        "learning_rate",
        "batch_size",
        "epochs",
        "early_stopping_patience",
    }
    if set(raw) != required or raw["schema_version"] != 2:
        raise ValueError("training configuration fields do not match schema v2")
    split_raw = _object(raw["split"], "split")
    preprocessing_raw = _object(raw["preprocessing"], "preprocessing")
    augmentation = _object(raw["augmentation"], "augmentation")
    selection = _object(raw["selection"], "selection")
    if split_raw.get("strategy") != "deterministic_stratified_related-group-hash":
        raise ValueError("unsupported split strategy")
    if augmentation.get("seed_strategy") != "sha256(global_seed:epoch:sample_identity)":
        raise ValueError("unsupported augmentation seed strategy")
    if selection != {
        "schema_version": 1,
        "rule_version": "agrimind-cv-validation-selection-v1",
        "primary_metric": "macro_f1",
        "secondary_metric": "accuracy",
        "tie_preference": "mean_rgb_centroid_baseline",
    }:
        raise ValueError("unsupported model-selection policy")
    training = TrainingConfig(
        schema_version=2,
        config_version=str(raw["training_config_version"]),
        architecture=str(raw["architecture"]),
        pretrained_weights=str(raw["pretrained_weights"])
        if raw["pretrained_weights"] is not None
        else None,
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
        mean=tuple(float(value) for value in preprocessing_raw["mean"]),  # type: ignore[arg-type]
        std=tuple(float(value) for value in preprocessing_raw["std"]),  # type: ignore[arg-type]
    )
    return raw, training, split, preprocessing


def _write_once(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists; refusing to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return file_digest(path)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    if args.command == "official-evaluate":
        payload = run_official_evaluation(
            OfficialPaths(
                dataset_config=args.dataset_config,
                training_config=args.training_config,
                official_config=args.official_config,
                dataset_root=args.dataset_root,
                source_archive=args.source_archive,
                audit_report=args.audit_report,
                related_manifest=args.related_manifest,
                split_manifest=args.split_manifest,
                artifact=args.model,
                runtime_manifest=args.runtime_manifest,
                evaluation_report=args.evaluation_report,
                test_opening_marker=args.test_opening_marker,
                runtime_schema=ROOT
                / "ai/computer_vision/data_contracts/runtime-model.v1.schema.json",
                evaluation_schema=ROOT
                / "ai/computer_vision/data_contracts/official-evaluation.v1.schema.json",
                repository_root=ROOT,
            )
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.audit_report.exists() or args.related_manifest.exists():
        raise FileExistsError("audit output already exists; refusing partial overwrite")
    if args.command == "train":
        destinations = (
            args.split_manifest,
            args.model,
            args.metadata,
        )
        if any(path.exists() for path in destinations):
            raise FileExistsError(
                "official training output already exists; refusing partial overwrite"
            )
    dataset = DatasetConfig.load(args.dataset_config)
    evidence = verify_source(
        args.dataset_root,
        dataset,
        archive=args.source_archive,
        evidence_file=args.source_evidence,
    )
    report = audit_dataset(args.dataset_root, dataset, source_evidence=evidence)
    _write_once(args.audit_report, report_as_dict(report))
    if report.valid_for_manifest:
        write_related_manifest(report, args.related_manifest)
    if args.command == "audit":
        print(json.dumps(report_as_dict(report), indent=2, sort_keys=True))
        return 0 if report.valid_for_manifest else 1
    if not report.valid_for_manifest:
        raise ValueError("dataset audit failed; refusing official training")
    if evidence.status != SourceVerificationStatus.VERIFIED:
        raise ValueError("official training requires VERIFIED dataset source evidence")

    raw, training, split_config, preprocessing = _training_components(args.training_config)
    split = deterministic_group_split(report.samples, split_config)
    assert_no_candidate_leakage(report.samples, report.near_duplicate_candidates, split)
    write_split_manifest(report.samples, split, args.split_manifest)
    baseline = train_mean_rgb_centroid_baseline(args.dataset_root, report.eligible_samples, split)

    candidate_path = args.model.with_name(args.model.stem + ".candidate" + args.model.suffix)
    candidate = train_and_validate(
        dataset_root=args.dataset_root,
        samples=report.eligible_samples,
        split=split,
        config=training,
        preprocessing=preprocessing,
        model_destination=candidate_path,
    )
    selection = select_model(baseline.metrics, candidate.metrics)
    if args.model.exists():
        raise FileExistsError("selected model destination already exists")
    if selection.selected_model == BASELINE_ID:
        candidate_path.unlink()
        write_baseline_artifact(baseline, args.model)
        artifact_format = "mean_rgb_centroids_v1"
        architecture = "mean_rgb_centroid"
        weights = None
    else:
        os.replace(candidate_path, args.model)
        artifact_format = "pytorch_state_dict"
        architecture = training.architecture
        weights = training.pretrained_weights

    git = repository_git_state(ROOT)
    torch, _ = load_training_runtime()
    torch_runtime = cast(Any, torch)
    metadata = ArtifactMetadata(
        schema_version=2,
        artifact_id=args.artifact_id,
        artifact_version=args.artifact_version,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        code_revision=git.revision,
        git_dirty=git.dirty,
        artifact={
            "format": artifact_format,
            "path": args.model.as_posix(),
            "size_bytes": args.model.stat().st_size,
            "sha256": _sha(args.model),
        },
        selected_model=selection.selected_model,
        architecture=architecture,
        pretrained_weights=weights,
        label_map_version=LABEL_MAP_VERSION,
        label_mapping={"NORMAL": 0, "ANOMALY": 1},
        preprocessing_contract_version=(
            BASELINE_PREPROCESSING_VERSION
            if selection.selected_model == BASELINE_ID
            else preprocessing.contract_version
        ),
        dataset={
            "id": dataset.dataset_id,
            "version": dataset.dataset_version,
            "fingerprint": report.dataset_fingerprint,
            "config_sha256": _sha(args.dataset_config),
            "source_verification": evidence.status.value,
            "source_evidence": asdict(evidence),
        },
        related_manifest_fingerprint=report.related_manifest_fingerprint,
        split={
            "contract_version": split_config.contract_version,
            "fingerprint": split.fingerprint,
            "seed": split_config.seed,
            "ratios": {
                "train": split_config.train,
                "validation": split_config.validation,
                "test": split_config.test,
            },
            "counts": split.counts,
            "class_counts": split.class_counts,
        },
        training={
            "config_version": training.config_version,
            "config_sha256": _sha(args.training_config),
            "random_seed": training.seed,
            "resolved_config": raw,
            "outcome": {
                "epochs_executed": candidate.epochs_executed,
                "best_epoch": candidate.best_epoch,
                "stopped_early": candidate.stopped_early,
                "class_weights": list(candidate.class_weights),
                "duration_seconds": candidate.duration_seconds,
            },
        },
        runtime={
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "pillow": importlib.metadata.version("Pillow"),
            "torch": importlib.metadata.version("torch"),
            "torchvision": importlib.metadata.version("torchvision"),
            "platform": platform.platform(),
            "device": candidate.device,
            "cuda": getattr(torch_runtime.version, "cuda", None),
            "cudnn": (
                torch_runtime.backends.cudnn.version()
                if hasattr(torch_runtime.backends, "cudnn")
                else None
            ),
            "deterministic_settings": {
                "torch_deterministic_algorithms": True,
                "cudnn_deterministic": True,
                "cudnn_benchmark": False,
                "data_loader_workers": 0,
            },
        },
        evaluation={
            "baseline_validation": asdict(baseline.metrics),
            "candidate_validation": asdict(candidate.metrics),
            "selection_rule_version": selection.rule_version,
            "selection_reason": selection.reason,
            "test_evaluated": False,
            "threshold_selection": "DEFERRED_TO_AGM_031",
        },
    )
    write_metadata(
        metadata,
        args.metadata,
        schema_path=SCHEMA,
        model_path=args.model,
        cleanup_model_on_failure=True,
    )
    print(
        json.dumps(
            {
                "selected_model": selection.selected_model,
                "test_evaluated": False,
                "metadata": str(args.metadata),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
