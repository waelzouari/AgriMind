"""Versioned image preprocessing shared by training and future inference."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps


@dataclass(frozen=True, slots=True)
class PreprocessingContract:
    schema_version: int = 1
    contract_version: str = "agrimind-cv-mobilenet-v2-preprocessing-v1"
    width: int = 224
    height: int = 224
    color_mode: str = "RGB"
    dtype: str = "float32"
    layout: str = "CHW"
    resize: str = "fit_center_crop"
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if (
            self.schema_version != 1
            or self.contract_version != "agrimind-cv-mobilenet-v2-preprocessing-v1"
        ):
            raise ValueError("unsupported preprocessing contract")
        if (self.color_mode, self.dtype, self.layout, self.resize) != (
            "RGB",
            "float32",
            "CHW",
            "fit_center_crop",
        ):
            raise ValueError("unsupported MobileNetV2 preprocessing semantics")
        if len(self.mean) != 3 or len(self.std) != 3 or any(value <= 0 for value in self.std):
            raise ValueError("preprocessing mean/std must contain three valid channels")


def preprocess_evaluation(
    image: Image.Image, contract: PreprocessingContract
) -> NDArray[np.float32]:
    rgb = image.convert(contract.color_mode)
    fitted = ImageOps.fit(rgb, (contract.width, contract.height), method=Image.Resampling.BILINEAR)
    array = np.asarray(fitted, dtype=np.float32) / 255.0
    normalized = (array - np.asarray(contract.mean)) / np.asarray(contract.std)
    return np.transpose(normalized, (2, 0, 1)).astype(np.float32)


def preprocess_training(
    image: Image.Image,
    contract: PreprocessingContract,
    *,
    global_seed: int,
    epoch: int,
    sample_identity: str,
    horizontal_flip_probability: float = 0.5,
) -> NDArray[np.float32]:
    if not 0 <= horizontal_flip_probability <= 1:
        raise ValueError("flip probability must be between zero and one")
    transformed = image
    if epoch < 0 or not sample_identity:
        raise ValueError("epoch and sample identity are required for augmentation")
    material = f"{global_seed}:{epoch}:{sample_identity}".encode()
    derived_seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    if random.Random(derived_seed).random() < horizontal_flip_probability:
        transformed = ImageOps.mirror(image)
    return preprocess_evaluation(transformed, contract)
