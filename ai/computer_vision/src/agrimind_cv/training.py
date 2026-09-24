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

from agrimind_cv.contracts import CanonicalLabel, Sample
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
    architecture: str = "mobilenet_v2"
    pretrained_weights: str | None = "IMAGENET1K_V1"
    seed: int = 20260923
    epochs: int = 10
    batch_size: int = 32
    learning_rate: float = 0.001
    early_stopping_patience: int = 3

    def __post_init__(self) -> None:
        if self.architecture != "mobilenet_v2":
            raise ValueError("only the approved MobileNetV2 candidate is supported")
        if (
            self.seed < 0
            or self.epochs <= 0
            or self.batch_size <= 0
            or self.learning_rate <= 0
            or self.early_stopping_patience <= 0
        ):
            raise ValueError("training seed and hyperparameters must be positive")


@dataclass(frozen=True, slots=True)
class TrainingOutcome:
    metrics: MetricsReport
    epochs_executed: int
    best_epoch: int
    stopped_early: bool
    class_weights: tuple[float, float]
    duration_seconds: float
    device: str


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
    if hasattr(torch, "use_deterministic_algorithms"):
        torch.use_deterministic_algorithms(True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    label_index = {
        CanonicalLabel.NORMAL: 0,
        CanonicalLabel.ANOMALY: 1,
    }

    class ManifestDataset:
        def __init__(self, items: list[Sample], *, training: bool) -> None:
            self.items = items
            self.training = training

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> tuple[Any, int]:
            sample = self.items[index]
            with Image.open(sample.resolved_path(dataset_root)) as image:
                array = (
                    preprocess_training(image, preprocessing, seed=config.seed + index)
                    if self.training
                    else preprocess_evaluation(image, preprocessing)
                )
            return torch.from_numpy(array), label_index[sample.canonical_label]

    partitions = {
        name: [item for item in samples if split.assignments[item.relative_path] == name]
        for name in ("train", "validation", "test")
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
    loader = torch.utils.data.DataLoader(
        ManifestDataset(partitions["train"], training=True),
        batch_size=config.batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(config.seed),
    )
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


def training_config_as_dict(config: TrainingConfig) -> dict[str, object]:
    return asdict(config)
