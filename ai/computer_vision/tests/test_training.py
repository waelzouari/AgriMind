import pytest

from agrimind_cv.training import TrainingConfig


def test_training_configuration_is_bounded() -> None:
    assert TrainingConfig().architecture == "mobilenet_v2"
    with pytest.raises(ValueError, match="approved"):
        TrainingConfig(architecture="huge-model")
    with pytest.raises(ValueError, match="version"):
        TrainingConfig(config_version="unknown")
    with pytest.raises(ValueError, match="flip"):
        TrainingConfig(horizontal_flip_probability=2.0)
    with pytest.raises(ValueError, match="optimizer"):
        TrainingConfig(optimizer="SGD")
