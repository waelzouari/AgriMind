from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from agrimind_ingestion.application.acknowledgements import (
    IngestionAcknowledgementFactory,
)
from agrimind_ingestion.domain import IngestionOutcome, IngestionResult, MessageKind

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
FARM = UUID("11111111-1111-4111-8111-111111111111")
DEVICE = UUID("22222222-2222-4222-8222-222222222222")
MESSAGE = UUID("33333333-3333-4333-8333-333333333333")


def result(outcome: IngestionOutcome, reason: str) -> IngestionResult:
    return IngestionResult(outcome, reason, MESSAGE, DEVICE, FARM, MessageKind.TELEMETRY)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (IngestionOutcome.INSERTED, "persisted"),
        (IngestionOutcome.DUPLICATE, "duplicate"),
    ],
)
def test_positive_terminal_results_create_qos1_nonretained_receipt(
    outcome: IngestionOutcome, expected: str
) -> None:
    publication = IngestionAcknowledgementFactory(clock=lambda: NOW).create(
        result(outcome, outcome.value)
    )

    assert publication is not None
    assert publication.topic.endswith(f"/sync/acks/{MESSAGE}")
    assert publication.qos == 1
    assert publication.retain is False
    assert json.loads(publication.payload)["status"] == expected


def test_correlatable_rejection_is_bounded_and_retryable_or_uncorrelatable_is_silent() -> None:
    factory = IngestionAcknowledgementFactory(clock=lambda: NOW)
    rejected = factory.create(result(IngestionOutcome.REJECTED, "device_farm_mismatch"))
    retryable = factory.create(result(IngestionOutcome.RETRYABLE, "persistence_unavailable"))
    uncorrelatable = factory.create(IngestionResult(IngestionOutcome.REJECTED, "malformed_json"))

    assert rejected is not None
    payload = json.loads(rejected.payload)
    assert payload["status"] == "rejected"
    assert payload["reason_code"] == "farm_mismatch"
    assert retryable is None
    assert uncorrelatable is None
