"""Optional MobileNetV2 training boundary.

Torch is imported only when full training is requested, keeping ordinary CI
CPU-only, offline, and lightweight.
"""

from __future__ import annotations

import copy
import importlib
import logging
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from agrimind_cv.contracts import CanonicalLabel, Partition, Sample
from agrimind_cv.metrics import MetricsReport, classification_metrics
from agrimind_cv.preprocessing import (
    PreprocessingContract,
    preprocess_evaluation,
    preprocess_training,
)
from agrimind_cv.split import SplitResult


class TrainingDependencyError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    schema_version: int = 2
    config_version: str = "agrimind-cv-mobilenet-v2-training-v1"
    architecture: str = "mobilenet_v2"
    pretrained_weights: str | None = "IMAGENET1K_V1"
    seed: int = 20260923
    epochs: int = 10
    batch_size: int = 32
    learning_rate: float = 0.001
    early_stopping_patience: int = 3
    horizontal_flip_probability: float = 0.5
    optimizer: str = "Adam"

    def __post_init__(self) -> None:
        if self.architecture != "mobilenet_v2":
            raise ValueError("only the approved MobileNetV2 candidate is supported")
        if self.optimizer != "Adam":
            raise ValueError("only the versioned Adam optimizer is supported")
        if (
            self.seed < 0
            or self.epochs <= 0
            or self.batch_size <= 0
            or self.learning_rate <= 0
            or self.early_stopping_patience <= 0
        ):
            raise ValueError("training seed and hyperparameters must be positive")
        if (
            self.schema_version != 2
            or self.config_version != "agrimind-cv-mobilenet-v2-training-v1"
        ):
            raise ValueError("unsupported training configuration version")
        if not 0 <= self.horizontal_flip_probability <= 1:
            raise ValueError("horizontal flip probability must be between zero and one")


@dataclass(frozen=True, slots=True)
class TrainingOutcome:
    metrics: MetricsReport
    epochs_executed: int
    best_epoch: int
    stopped_early: bool
    class_weights: tuple[float, float]
    duration_seconds: float
    device: str


@dataclass(frozen=True, slots=True)
class PartitionScores:
    relative_paths: tuple[str, ...]
    source_labels: tuple[str, ...]
    expected: tuple[str, ...]
    anomaly_softmax_probabilities: tuple[float, ...]
    duration_seconds: float


def load_training_runtime() -> tuple[object, object]:
    try:
        return importlib.import_module("torch"), importlib.import_module("torchvision")
    except ModuleNotFoundError as error:
        raise TrainingDependencyError(
            "training dependencies are absent; install agrimind-cv[train] explicitly"
        ) from error


def _runtime() -> tuple[Any, Any]:
    torch, torchvision = load_training_runtime()
    return torch, torchvision


def train_and_validate(
    *,
    dataset_root: Path,
    samples: tuple[Sample, ...],
    split: SplitResult,
    config: TrainingConfig,
    preprocessing: PreprocessingContract,
    model_destination: Path,
    device_name: str | None = None,
) -> TrainingOutcome:
    """Train MobileNetV2 and report validation evidence for AGM-030.

    This full-data operation is intentionally absent from ordinary CI. It never
    downloads a dataset; pretrained weights may download only when explicitly
    configured by the operator.
    """
    torch, torchvision = _runtime()
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    if hasattr(torch, "use_deterministic_algorithms"):
        torch.use_deterministic_algorithms(True)
    device = torch.device(
        device_name if device_name is not None else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    label_index = {
        CanonicalLabel.NORMAL: 0,
        CanonicalLabel.ANOMALY: 1,
    }

    class ManifestDataset:
        def __init__(self, items: list[Sample], *, training: bool) -> None:
            self.items = items
            self.training = training
            self.epoch = 0

        def set_epoch(self, epoch: int) -> None:
            self.epoch = epoch

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> tuple[Any, int]:
            sample = self.items[index]
            with Image.open(sample.resolved_path(dataset_root)) as image:
                array = (
                    preprocess_training(
                        image,
                        preprocessing,
                        global_seed=config.seed,
                        epoch=self.epoch,
                        sample_identity=sample.relative_path,
                        horizontal_flip_probability=config.horizontal_flip_probability,
                    )
                    if self.training
                    else preprocess_evaluation(image, preprocessing)
                )
            return torch.from_numpy(array), label_index[sample.canonical_label]

    partitions = {
        name: [item for item in samples if split.assignments[item.relative_path] == partition]
        for name, partition in (
            ("train", Partition.TRAIN),
            ("validation", Partition.VALIDATION),
        )
    }
    weights = None
    if config.pretrained_weights is not None:
        weights = torchvision.models.MobileNet_V2_Weights[config.pretrained_weights]
    model = torchvision.models.mobilenet_v2(weights=weights)
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, 2)
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    train_counts = [
        sum(label_index[item.canonical_label] == index for item in partitions["train"])
        for index in range(2)
    ]
    if any(count == 0 for count in train_counts):
        raise ValueError("training partition must contain both canonical labels")
    class_weights = torch.tensor(
        [len(partitions["train"]) / (2 * count) for count in train_counts],
        dtype=torch.float32,
        device=device,
    )
    loss_function = torch.nn.CrossEntropyLoss(weight=class_weights)
    training_dataset = ManifestDataset(partitions["train"], training=True)
    validation_loader = torch.utils.data.DataLoader(
        ManifestDataset(partitions["validation"], training=False),
        batch_size=config.batch_size,
    )
    best_validation_loss = float("inf")
    best_state = None
    best_epoch = 0
    epochs_without_improvement = 0
    started = time.perf_counter()
    epochs_executed = 0
    for epoch in range(1, config.epochs + 1):
        training_dataset.set_epoch(epoch)
        loader = torch.utils.data.DataLoader(
            training_dataset,
            batch_size=config.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(config.seed + epoch),
            num_workers=0,
        )
        model.train()
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            loss = loss_function(model(inputs), targets)
            loss.backward()
            optimizer.step()
        model.eval()
        validation_loss = 0.0
        validation_samples = 0
        with torch.no_grad():
            for inputs, targets in validation_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                batch_loss = loss_function(model(inputs), targets)
                validation_loss += float(batch_loss.item()) * len(targets)
                validation_samples += len(targets)
        if validation_samples == 0:
            raise ValueError("validation partition must not be empty")
        validation_loss /= validation_samples
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        epochs_executed = epoch
        logging.getLogger(__name__).info(
            "epoch=%d validation_loss=%.6f best_epoch=%d", epoch, validation_loss, best_epoch
        )
        if epochs_without_improvement >= config.early_stopping_patience:
            break
    if best_state is None:
        raise RuntimeError("training did not produce a model checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    actual: list[str] = []
    predicted: list[str] = []
    evaluation_loader = torch.utils.data.DataLoader(
        ManifestDataset(partitions["validation"], training=False), batch_size=config.batch_size
    )
    names = (CanonicalLabel.NORMAL.value, CanonicalLabel.ANOMALY.value)
    with torch.no_grad():
        for inputs, targets in evaluation_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            guesses = model(inputs).argmax(dim=1)
            actual.extend(names[int(value)] for value in targets.tolist())
            predicted.extend(names[int(value)] for value in guesses.tolist())
    metrics = classification_metrics(actual, predicted, names)
    model_destination.parent.mkdir(parents=True, exist_ok=True)
    if model_destination.exists():
        raise FileExistsError("model artifact already exists; refusing to overwrite")
    temporary = model_destination.with_suffix(model_destination.suffix + ".tmp")
    model.to("cpu")
    torch.save(model.state_dict(), temporary)
    temporary.replace(model_destination)
    return TrainingOutcome(
        metrics=metrics,
        epochs_executed=epochs_executed,
        best_epoch=best_epoch,
        stopped_early=epochs_executed < config.epochs,
        class_weights=(float(class_weights[0].item()), float(class_weights[1].item())),
        duration_seconds=time.perf_counter() - started,
        device=str(device),
    )


def score_partition(
    *,
    dataset_root: Path,
    samples: tuple[Sample, ...],
    split: SplitResult,
    partition: Partition,
    config: TrainingConfig,
    preprocessing: PreprocessingContract,
    model_path: Path,
) -> PartitionScores:
    """Score one deterministic partition with an already frozen CPU artifact."""
    torch, torchvision = _runtime()
    selected = tuple(
        sorted(
            (sample for sample in samples if split.assignments[sample.relative_path] == partition),
            key=lambda sample: sample.relative_path,
        )
    )
    if not selected:
        raise ValueError(f"{partition.value} partition must not be empty")

    model = torchvision.models.mobilenet_v2(weights=None)
    model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, 2)
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()

    probabilities: list[float] = []
    started = time.perf_counter()
    with torch.no_grad():
        for offset in range(0, len(selected), config.batch_size):
            batch = selected[offset : offset + config.batch_size]
            tensors = []
            for sample in batch:
                with Image.open(sample.resolved_path(dataset_root)) as image:
                    tensors.append(torch.from_numpy(preprocess_evaluation(image, preprocessing)))
            logits = model(torch.stack(tensors))
            if tuple(logits.shape) != (len(batch), 2):
                raise RuntimeError("frozen model output shape is invalid")
            probabilities.extend(float(value) for value in torch.softmax(logits, dim=1)[:, 1])
    return PartitionScores(
        relative_paths=tuple(sample.relative_path for sample in selected),
        source_labels=tuple(sample.source_label for sample in selected),
        expected=tuple(sample.canonical_label.value for sample in selected),
        anomaly_softmax_probabilities=tuple(probabilities),
        duration_seconds=time.perf_counter() - started,
    )


def training_config_as_dict(config: TrainingConfig) -> dict[str, object]:
    return asdict(config)
