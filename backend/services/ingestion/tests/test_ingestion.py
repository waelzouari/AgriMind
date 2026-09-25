from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fakes import FakePersistence, FakeRegistry

from agrimind_ingestion.application.ingestion import IngestionService
from agrimind_ingestion.contracts import MAX_INBOUND_MQTT_PAYLOAD_BYTES, ContractValidator
from agrimind_ingestion.domain import (
    DeviceRegistration,
    IngestionOutcome,
    PersistenceRejected,
    PersistenceUnavailable,
)

ROOT = Path(__file__).resolve().parents[4]
CONTRACTS = ROOT / "contracts" / "v1"
NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
FARM_A = UUID("11111111-1111-4111-8111-111111111111")
FARM_B = UUID("99999999-9999-4999-8999-999999999999")
DEVICE = UUID("22222222-2222-4222-8222-222222222222")


def telemetry_payload(**changes: object) -> bytes:
    payload: dict[str, object] = {
        "schema_version": 1,
        "message_id": "33333333-3333-4333-8333-333333333333",
        "farm_id": str(FARM_A),
        "device_id": str(DEVICE),
        "metric": "temperature",
        "value": 22.5,
        "unit": "°C",
        "recorded_at": "2026-09-23T12:00:00Z",
        "quality": "valid",
    }
    payload.update(changes)
    return json.dumps(payload).encode()


def status_payload(**changes: object) -> bytes:
    payload: dict[str, object] = {
        "schema_version": 1,
        "message_id": "44444444-4444-4444-8444-444444444444",
        "farm_id": str(FARM_A),
        "device_id": str(DEVICE),
        "online": True,
        "pump_state": False,
        "health": "healthy",
        "recorded_at": "2026-09-23T12:00:00Z",
        "uptime_seconds": 30,
        "firmware_version": "0.1.0",
        "errors": [],
    }
    payload.update(changes)
    return json.dumps(payload).encode()


def acknowledgement_payload(**changes: object) -> bytes:
    payload: dict[str, object] = {
        "schema_version": 1,
        "acknowledgement_id": "55555555-5555-4555-8555-555555555555",
        "command_id": "66666666-6666-4666-8666-666666666666",
        "farm_id": str(FARM_A),
        "device_id": str(DEVICE),
        "status": "completed",
        "occurred_at": "2026-09-23T12:00:00Z",
        "pump_state": False,
    }
    payload.update(changes)
    return json.dumps(payload).encode()


def irrigation_result_payload(**changes: object) -> bytes:
    payload: dict[str, object] = {
        "schema_version": 1,
        "event_id": "77777777-7777-4777-8777-777777777777",
        "farm_id": str(FARM_A),
        "device_id": str(DEVICE),
        "soil_moisture_before": 40.0,
        "soil_moisture_after": 45.0,
        "delta": 5.0,
        "result": "increased",
        "completed_at": "2026-09-23T12:00:00Z",
    }
    payload.update(changes)
    return json.dumps(payload).encode()


def service(*, active: bool = True) -> tuple[IngestionService, FakeRegistry, FakePersistence]:
    registry = FakeRegistry({FARM_A, FARM_B})
    registry.devices[DEVICE] = DeviceRegistration(DEVICE, FARM_A, "edge", active)
    persistence = FakePersistence()
    instance = IngestionService(
        ContractValidator(CONTRACTS),
        registry,
        persistence,
        clock=lambda: NOW,
    )
    return instance, registry, persistence


def telemetry_topic(farm: UUID = FARM_A, device: UUID = DEVICE) -> str:
    return f"agrimind/v1/farms/{farm}/devices/{device}/telemetry/temperature"


def status_topic(farm: UUID = FARM_A, device: UUID = DEVICE) -> str:
    return f"agrimind/v1/farms/{farm}/devices/{device}/status/device"


def acknowledgement_topic(farm: UUID = FARM_A, device: UUID = DEVICE) -> str:
    return f"agrimind/v1/farms/{farm}/devices/{device}/acks/66666666-6666-4666-8666-666666666666"


def irrigation_result_topic(farm: UUID = FARM_A, device: UUID = DEVICE) -> str:
    return f"agrimind/v1/farms/{farm}/devices/{device}/events/irrigation_result"


def test_active_registered_telemetry_and_status_are_persisted() -> None:
    instance, _, persistence = service()

    telemetry = instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False)
    status = instance.process(status_topic(), status_payload(), qos=1, retain=True)

    assert telemetry.outcome is IngestionOutcome.INSERTED
    assert status.outcome is IngestionOutcome.INSERTED
    assert persistence.telemetry[0]["farm_id"] == str(FARM_A)
    assert len(persistence.statuses) == 1


def test_acknowledgement_and_measured_irrigation_result_are_persisted_separately() -> None:
    instance, _, persistence = service()

    acknowledgement = instance.process(
        acknowledgement_topic(), acknowledgement_payload(), qos=1, retain=False
    )
    result = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )

    assert acknowledgement.outcome is IngestionOutcome.INSERTED
    assert result.outcome is IngestionOutcome.INSERTED
    assert persistence.acknowledgements[0]["status"] == "completed"
    assert persistence.irrigation_results[0]["result"] == "increased"


@pytest.mark.parametrize(
    ("topic", "payload", "qos", "retain", "reason"),
    [
        (acknowledgement_topic(), acknowledgement_payload(), 0, False, "invalid_qos"),
        (acknowledgement_topic(), acknowledgement_payload(), 1, True, "retained_event"),
        (
            acknowledgement_topic(),
            acknowledgement_payload(command_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            1,
            False,
            "topic_payload_command_mismatch",
        ),
        (
            irrigation_result_topic(),
            irrigation_result_payload(delta=4.0),
            1,
            False,
            "invalid_contract",
        ),
    ],
)
def test_feedback_event_contract_failures_are_permanent(
    topic: str, payload: bytes, qos: int, retain: bool, reason: str
) -> None:
    instance, _, persistence = service()

    result = instance.process(topic, payload, qos=qos, retain=retain)

    assert result.outcome is IngestionOutcome.REJECTED
    assert result.reason_code == reason
    assert persistence.acknowledgements == []
    assert persistence.irrigation_results == []


@pytest.mark.parametrize(
    ("topic", "payload", "reason"),
    [
        ("invalid", telemetry_payload(), "invalid_topic"),
        (telemetry_topic(), b"{", "malformed_json"),
        (
            telemetry_topic(),
            telemetry_payload()[:-1] + b',"metric":"temperature"}',
            "malformed_json",
        ),
        (telemetry_topic(), telemetry_payload(metric="unknown"), "invalid_contract"),
        (telemetry_topic(), telemetry_payload(unit="%"), "invalid_contract"),
        (telemetry_topic(), telemetry_payload(value=float("inf")), "malformed_json"),
        (
            telemetry_topic(),
            telemetry_payload(device_id=str(UUID(int=7))),
            "topic_payload_device_mismatch",
        ),
        (telemetry_topic(FARM_B), telemetry_payload(), "topic_payload_farm_mismatch"),
        (telemetry_topic(), telemetry_payload(recorded_at="2026-09-22T11:59:59Z"), "stale_message"),
        (
            telemetry_topic(),
            telemetry_payload(recorded_at="2026-09-23T12:05:01Z"),
            "future_message",
        ),
    ],
)
def test_permanent_validation_rejections(topic: str, payload: bytes, reason: str) -> None:
    instance, _, persistence = service()

    result = instance.process(topic, payload, qos=1, retain=False)

    assert result.outcome is IngestionOutcome.REJECTED
    assert result.reason_code == reason
    assert persistence.telemetry == []


@pytest.mark.parametrize(
    "size", [MAX_INBOUND_MQTT_PAYLOAD_BYTES - 1, MAX_INBOUND_MQTT_PAYLOAD_BYTES]
)
def test_payload_at_or_below_limit_reaches_contract_validation(size: int) -> None:
    instance, registry, persistence = service()
    registry.get = Mock(wraps=registry.get)
    payload = telemetry_payload()
    padded = payload + (b" " * (size - len(payload)))

    result = instance.process(telemetry_topic(), padded, qos=1, retain=False)

    assert result.outcome is IngestionOutcome.INSERTED
    assert registry.get.call_count == 1
    assert len(persistence.telemetry) == 1


@pytest.mark.parametrize(
    "payload",
    [
        telemetry_payload()
        + b" " * (MAX_INBOUND_MQTT_PAYLOAD_BYTES + 1 - len(telemetry_payload())),
        b"\xff" * (MAX_INBOUND_MQTT_PAYLOAD_BYTES + 1),
    ],
)
def test_oversized_payload_is_permanently_rejected_before_registry_and_persistence(
    payload: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    instance, registry, persistence = service()
    registry.get = Mock(wraps=registry.get)

    with caplog.at_level(logging.INFO):
        result = instance.process(telemetry_topic(), payload, qos=1, retain=False)

    assert result.outcome is IngestionOutcome.REJECTED
    assert result.reason_code == "payload_too_large"
    assert result.terminal is True
    assert result.message_id is None
    registry.get.assert_not_called()
    assert persistence.telemetry == []
    assert caplog.records[-1].reason_code == "payload_too_large"
    assert telemetry_payload().decode() not in caplog.text


def test_unknown_inactive_and_registry_cross_farm_devices_are_rejected() -> None:
    instance, registry, _ = service()
    registry.devices.clear()
    unknown = instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False)
    assert unknown.reason_code == "unknown_device"
    assert unknown.correlatable_telemetry is True

    registry.devices[DEVICE] = DeviceRegistration(DEVICE, FARM_A, None, False)
    inactive = instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False)
    assert inactive.reason_code == "inactive_device"
    assert inactive.correlatable_telemetry is True

    registry.devices[DEVICE] = DeviceRegistration(DEVICE, FARM_B, None, True)
    assert (
        instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False).reason_code
        == "device_farm_mismatch"
    )


def test_feedback_event_enforces_registry_authority_and_retry_semantics() -> None:
    instance, registry, persistence = service()
    registry.devices.clear()
    unknown = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )
    assert unknown.reason_code == "unknown_device"
    assert unknown.correlatable_event is True

    registry.devices[DEVICE] = DeviceRegistration(DEVICE, FARM_A, None, False)
    inactive = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )
    assert inactive.reason_code == "inactive_device"

    registry.devices[DEVICE] = DeviceRegistration(DEVICE, FARM_B, None, True)
    mismatch = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )
    assert mismatch.reason_code == "device_farm_mismatch"

    registry.devices[DEVICE] = DeviceRegistration(DEVICE, FARM_A, None, True)
    persistence.outcome = "duplicate"
    duplicate = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )
    assert duplicate.outcome is IngestionOutcome.DUPLICATE

    persistence.failure = PersistenceRejected("message_id_conflict")
    conflict = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )
    assert conflict.outcome is IngestionOutcome.REJECTED
    assert conflict.reason_code == "message_id_conflict"

    persistence.failure = PersistenceUnavailable("offline")
    unavailable = instance.process(
        irrigation_result_topic(), irrigation_result_payload(), qos=1, retain=False
    )
    assert unavailable.outcome is IngestionOutcome.RETRYABLE
    assert unavailable.terminal is False


def test_retained_telemetry_and_wrong_qos_are_rejected_but_retained_status_is_allowed() -> None:
    instance, _, _ = service()
    assert (
        instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=True).reason_code
        == "retained_telemetry"
    )
    assert (
        instance.process(telemetry_topic(), telemetry_payload(), qos=0, retain=False).reason_code
        == "invalid_qos"
    )
    assert (
        instance.process(status_topic(), status_payload(), qos=1, retain=True).outcome
        is IngestionOutcome.INSERTED
    )


def test_duplicate_is_success_conflict_is_permanent_and_outage_is_retryable() -> None:
    instance, _, persistence = service()
    persistence.outcome = "duplicate"
    duplicate = instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False)
    assert duplicate.outcome is IngestionOutcome.DUPLICATE

    persistence.failure = PersistenceRejected("message_id_conflict")
    conflict = instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False)
    assert conflict.outcome is IngestionOutcome.REJECTED
    assert conflict.reason_code == "message_id_conflict"

    persistence.failure = PersistenceUnavailable("offline")
    unavailable = instance.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False)
    assert unavailable == unavailable.__class__(
        IngestionOutcome.RETRYABLE, "persistence_unavailable"
    )
    assert unavailable.terminal is False


def test_restart_redelivery_is_deterministic_with_durable_store_outcome() -> None:
    first, registry, persistence = service()
    assert (
        first.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False).outcome
        is IngestionOutcome.INSERTED
    )

    persistence.outcome = "duplicate"
    restarted = IngestionService(
        ContractValidator(CONTRACTS),
        registry,
        persistence,
        clock=lambda: NOW,
    )
    assert (
        restarted.process(telemetry_topic(), telemetry_payload(), qos=1, retain=False).outcome
        is IngestionOutcome.DUPLICATE
    )


def test_logs_do_not_include_payload_or_secret(caplog: pytest.LogCaptureFixture) -> None:
    instance, _, _ = service()
    secret = "do-not-log-this-secret"  # pragma: allowlist secret
    with caplog.at_level(logging.INFO):
        instance.process(telemetry_topic(), telemetry_payload(extra=secret), qos=1, retain=False)
    assert secret not in caplog.text
    assert caplog.records[-1].reason_code == "invalid_contract"
