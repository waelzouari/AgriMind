import numpy as np
from PIL import Image

from agrimind_cv.preprocessing import (
    PreprocessingContract,
    preprocess_evaluation,
    preprocess_training,
)


def test_evaluation_preprocessing_is_rgb_chw_float32_and_deterministic() -> None:
    image = Image.new("L", (20, 10), 128)
    contract = PreprocessingContract(width=8, height=6)
    first = preprocess_evaluation(image, contract)
    second = preprocess_evaluation(image, contract)
    assert first.shape == (3, 6, 8)
    assert first.dtype == np.float32
    assert np.array_equal(first, second)


def test_training_augmentation_is_seeded_and_separate() -> None:
    image = Image.new("RGB", (20, 10), (0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0))
    contract = PreprocessingContract(width=20, height=10)
    assert np.array_equal(
        preprocess_training(image, contract, seed=7),
        preprocess_training(image, contract, seed=7),
    )
