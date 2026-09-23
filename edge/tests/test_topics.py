from uuid import UUID

import pytest

from agrimind_edge.contracts.enums import TelemetryMetric
from agrimind_edge.contracts.topics import TopicBuilder

FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
COMMAND_ID = UUID("33333333-3333-4333-8333-333333333333")


def test_topic_construction_is_centralized_lowercase_and_versioned() -> None:
    topics = TopicBuilder(FARM_ID, DEVICE_ID)

    assert topics.telemetry(TelemetryMetric.SOIL_MOISTURE) == (
        "agrimind/v1/farms/11111111-1111-4111-8111-111111111111/"
        "devices/22222222-2222-4222-8222-222222222222/telemetry/soil_moisture"
    )
    assert topics.pump_command().endswith("/commands/pump")
    assert topics.acknowledgement(COMMAND_ID).endswith(f"/acks/{COMMAND_ID}")
    assert topics.device_status().endswith("/status/device")
    assert topics.ingestion_acknowledgement(COMMAND_ID).endswith(f"/sync/acks/{COMMAND_ID}")
    assert topics.ingestion_acknowledgement_filter().endswith("/sync/acks/+")
    assert topics.irrigation_result().endswith("/events/irrigation_result")


def test_topic_builder_rejects_unknown_version() -> None:
    with pytest.raises(ValueError, match="unsupported topic version"):
        TopicBuilder(FARM_ID, DEVICE_ID, version="v2")
