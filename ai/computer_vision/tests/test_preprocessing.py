import numpy as np
import pytest
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
        preprocess_training(image, contract, global_seed=7, epoch=1, sample_identity="a"),
        preprocess_training(image, contract, global_seed=7, epoch=1, sample_identity="a"),
    )


def test_augmentation_probability_is_authoritative_and_epoch_sequence_varies() -> None:
    image = Image.new("RGB", (20, 10), (0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0))
    contract = PreprocessingContract(width=20, height=10)
    never = preprocess_training(
        image,
        contract,
        global_seed=42,
        epoch=0,
        sample_identity="sample",
        horizontal_flip_probability=0.0,
    )
    always = preprocess_training(
        image,
        contract,
        global_seed=42,
        epoch=0,
        sample_identity="sample",
        horizontal_flip_probability=1.0,
    )
    assert not np.array_equal(never, always)
    sequence = [
        preprocess_training(
            image,
            contract,
            global_seed=42,
            epoch=epoch,
            sample_identity="sample",
            horizontal_flip_probability=0.5,
        )
        for epoch in range(12)
    ]
    assert any(not np.array_equal(sequence[0], item) for item in sequence[1:])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"color_mode": "RGBA"},
        {"dtype": "float64"},
        {"layout": "HWC"},
        {"resize": "stretch"},
        {"contract_version": "unknown"},
        {"std": (1.0, 0.0, 1.0)},
    ],
)
def test_invalid_preprocessing_contract_fails(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PreprocessingContract(**kwargs)  # type: ignore[arg-type]
