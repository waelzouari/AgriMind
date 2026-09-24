"""Command-line entrypoint for dataset auditing."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import platform
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from agrimind_cv.artifacts import ArtifactMetadata, write_metadata
from agrimind_cv.audit import audit_dataset, report_as_dict, write_manifest_csv
from agrimind_cv.baseline import evaluate_mean_rgb_centroid_baseline
from agrimind_cv.config import DatasetConfig, SplitConfig
from agrimind_cv.preprocessing import PreprocessingContract
from agrimind_cv.split import deterministic_group_split
from agrimind_cv.training import TrainingConfig, train_and_validate, training_config_as_dict


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="agrimind-cv")
    subcommands = result.add_subparsers(dest="command", required=True)
    audit = subcommands.add_parser("audit")
    audit.add_argument("--config", type=Path, required=True)
    audit.add_argument("--dataset-root", type=Path, required=True)
    audit.add_argument("--report", type=Path)
    audit.add_argument("--manifest", type=Path)
    train = subcommands.add_parser("train")
    train.add_argument("--dataset-config", type=Path, required=True)
    train.add_argument("--training-config", type=Path, required=True)
    train.add_argument("--dataset-root", type=Path, required=True)
    train.add_argument("--model", type=Path, required=True)
    train.add_argument("--metadata", type=Path, required=True)
    train.add_argument("--artifact-id", required=True)
    train.add_argument("--code-revision", required=True)
    return result


def _training_components(
    path: Path,
) -> tuple[dict[str, object], TrainingConfig, SplitConfig, PreprocessingContract]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("training configuration must be a schema v1 object")
    split_raw = raw["split"]
    preprocessing_raw = raw["preprocessing"]
    if not isinstance(split_raw, dict) or not isinstance(preprocessing_raw, dict):
        raise ValueError("split and preprocessing must be objects")
    training = TrainingConfig(
        architecture=str(raw["architecture"]),
        pretrained_weights=(
            str(raw["pretrained_weights"]) if raw["pretrained_weights"] is not None else None
        ),
        seed=int(raw["seed"]),
        epochs=int(raw["epochs"]),
        batch_size=int(raw["batch_size"]),
        learning_rate=float(raw["learning_rate"]),
        early_stopping_patience=int(raw["early_stopping_patience"]),
    )
    split = SplitConfig(
        train=float(split_raw["train"]),
        validation=float(split_raw["validation"]),
        test=float(split_raw["test"]),
        seed=training.seed,
        require_group_ids=bool(split_raw["require_group_ids"]),
    )
    preprocessing = PreprocessingContract(
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


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parser().parse_args(arguments)
    if args.command == "train":
        dataset = DatasetConfig.load(args.dataset_config)
        raw, training, split_config, preprocessing = _training_components(args.training_config)
        report = audit_dataset(args.dataset_root, dataset)
        if not report.valid_for_manifest:
            raise ValueError("dataset audit failed; refusing to train")
        split = deterministic_group_split(report.samples, split_config)
        baseline = evaluate_mean_rgb_centroid_baseline(args.dataset_root, report.samples, split)
        selected = train_and_validate(
            dataset_root=args.dataset_root,
            samples=report.samples,
            split=split,
            config=training,
            preprocessing=preprocessing,
            model_destination=args.model,
        )
        metadata = ArtifactMetadata(
            schema_version=1,
            artifact_id=args.artifact_id,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            code_revision=args.code_revision,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.dataset_version,
            dataset_fingerprint=report.fingerprint,
            split_fingerprint=split.fingerprint,
            training_config={
                **raw,
                "resolved": training_config_as_dict(training),
                "runtime": {
                    "python": platform.python_version(),
                    "torch": importlib.metadata.version("torch"),
                    "torchvision": importlib.metadata.version("torchvision"),
                },
            },
            architecture=training.architecture,
            pretrained_weights=training.pretrained_weights,
            preprocessing=asdict(preprocessing),
            label_mapping={"NORMAL": 0, "ANOMALY": 1},
            metrics={
                "baseline_validation": asdict(baseline),
                "model_validation": asdict(selected.metrics),
                "training_run": {
                    key: value for key, value in asdict(selected).items() if key != "metrics"
                },
            },
        )
        write_metadata(metadata, args.metadata)
        print(
            json.dumps(
                {
                    "dataset_fingerprint": report.fingerprint,
                    "split_fingerprint": split.fingerprint,
                    "split_counts": split.counts,
                    "split_class_counts": split.class_counts,
                    "model": str(args.model),
                    "metadata": str(args.metadata),
                },
                indent=2,
            )
        )
        return 0
    report = audit_dataset(args.dataset_root, DatasetConfig.load(args.config))
    rendered = json.dumps(report_as_dict(report), indent=2, sort_keys=True) + "\n"
    if args.report is None:
        print(rendered, end="")
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    if args.manifest is not None and report.valid_for_manifest:
        write_manifest_csv(report, args.manifest)
    return 0 if report.valid_for_manifest else 1


if __name__ == "__main__":
    raise SystemExit(main())
