import pytest

from agrimind_cv.training import TrainingConfig


def test_training_configuration_is_bounded() -> None:
    assert TrainingConfig().architecture == "mobilenet_v2"
    with pytest.raises(ValueError, match="approved"):
        TrainingConfig(architecture="huge-model")
