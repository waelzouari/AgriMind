from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from agrimind_edge.contracts.enums import (
    AcknowledgementStatus,
    DeviceHealth,
    IrrigationOutcome,
    PumpAction,
    TelemetryMetric,
)
from agrimind_edge.contracts.models import (
    CommandAcknowledgement,
    DeviceStatus,
    IrrigationResult,
    PumpCommand,
    Telemetry,
)

FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
MESSAGE_ID = UUID("33333333-3333-4333-8333-333333333333")
COMMAND_ID = UUID("44444444-4444-4444-8444-444444444444")
USER_ID = UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime(2026, 9, 22, 12, tzinfo=UTC)
CONTRACT_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "v1"


def _command_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "command_id": str(COMMAND_ID),
        "farm_id": str(FARM_ID),
        "device_id": str(DEVICE_ID),
        "action": "on",
        "duration_seconds": 30,
        "issued_at": "2026-09-22T12:00:00.000Z",
        "expires_at": "2026-09-22T12:01:00.000Z",
        "requested_by": str(USER_ID),
    }


def _json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_valid_v1_contracts_round_trip_deterministically() -> None:
    telemetry = Telemetry(
        message_id=MESSAGE_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        metric=TelemetryMetric.TEMPERATURE,
        value=28.5,
        unit="°C",
        recorded_at=NOW,
    )
    command = PumpCommand(
        command_id=COMMAND_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        action=PumpAction.ON,
        duration_seconds=30,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        requested_by=USER_ID,
    )
    acknowledgement = CommandAcknowledgement(
        acknowledgement_id=MESSAGE_ID,
        command_id=COMMAND_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        status=AcknowledgementStatus.ACCEPTED,
        occurred_at=NOW,
        pump_state=False,
    )
    status = DeviceStatus(
        message_id=MESSAGE_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        online=True,
        pump_state=False,
        health=DeviceHealth.HEALTHY,
        recorded_at=NOW,
        uptime_seconds=3600,
        firmware_version="0.1.0",
    )
    result = IrrigationResult(
        event_id=MESSAGE_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        soil_moisture_before=42.1,
        soil_moisture_after=68.3,
        delta=26.2,
        result=IrrigationOutcome.INCREASED,
        completed_at=NOW,
    )

    assert Telemetry.from_json(telemetry.to_json()) == telemetry
    assert PumpCommand.from_json(command.to_json(), now=NOW) == command
    assert CommandAcknowledgement.from_json(acknowledgement.to_json()) == acknowledgement
    assert DeviceStatus.from_json(status.to_json()) == status
    assert IrrigationResult.from_json(result.to_json()) == result
    assert telemetry.to_json() == telemetry.to_json()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.pop("command_id"), "missing required fields"),
        (lambda data: data.__setitem__("command_id", "not-a-uuid"), "canonical UUID"),
        (lambda data: data.__setitem__("action", "toggle"), "unsupported action"),
        (lambda data: data.__setitem__("schema_version", 2), "schema_version must be 1"),
        (lambda data: data.__setitem__("issued_at", "yesterday"), "RFC 3339"),
        (lambda data: data.__setitem__("duration_seconds", -1), "between 1 and 600"),
        (lambda data: data.__setitem__("duration_seconds", 601), "between 1 and 600"),
        (
            lambda data: data.__setitem__("expires_at", "2026-09-22T11:59:00.000Z"),
            "must be after",
        ),
        (lambda data: data.__setitem__("credential", "forbidden"), "unknown fields"),
    ],
)
def test_invalid_commands_are_rejected(mutation: object, message: str) -> None:
    payload = _command_payload()
    assert callable(mutation)
    mutation(payload)

    with pytest.raises(ValueError, match=message):
        PumpCommand.from_json(_json(payload), now=NOW)


def test_expired_command_is_rejected() -> None:
    with pytest.raises(ValueError, match="command has expired"):
        PumpCommand.from_json(_json(_command_payload()), now=NOW + timedelta(minutes=2))


def test_processing_deserializer_preserves_contract_but_defers_expiry() -> None:
    payload = _json(_command_payload())

    command = PumpCommand.from_json_without_expiry_validation(payload)

    assert command.command_id == COMMAND_ID
    with pytest.raises(ValueError, match="command has expired"):
        PumpCommand.from_json(payload, now=NOW + timedelta(minutes=2))


def test_processing_deserializer_keeps_structural_validation() -> None:
    payload = _command_payload()
    payload["action"] = "toggle"

    with pytest.raises(ValueError, match="unsupported action"):
        PumpCommand.from_json_without_expiry_validation(_json(payload))


def test_duplicate_json_fields_are_rejected() -> None:
    payload = _json(_command_payload())
    duplicate = payload[:-1] + ',"action":"off"}'

    with pytest.raises(ValueError, match="duplicate JSON field: action"):
        PumpCommand.from_json(duplicate, now=NOW)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_telemetry_is_rejected(value: float) -> None:
    payload = {
        "schema_version": 1,
        "message_id": str(MESSAGE_ID),
        "farm_id": str(FARM_ID),
        "device_id": str(DEVICE_ID),
        "metric": "temperature",
        "value": value,
        "unit": "°C",
        "recorded_at": "2026-09-22T12:00:00.000Z",
        "quality": "valid",
    }
    with pytest.raises(ValueError, match="must be finite"):
        Telemetry.from_json(_json(payload))


def test_metric_unit_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="unit for temperature"):
        Telemetry(
            message_id=MESSAGE_ID,
            farm_id=FARM_ID,
            device_id=DEVICE_ID,
            metric=TelemetryMetric.TEMPERATURE,
            value=20.0,
            unit="%",
            recorded_at=NOW,
        )


def test_acknowledgement_failure_requires_stable_reason_code() -> None:
    with pytest.raises(ValueError, match="reason_code is required"):
        CommandAcknowledgement(
            acknowledgement_id=MESSAGE_ID,
            command_id=COMMAND_ID,
            farm_id=FARM_ID,
            device_id=DEVICE_ID,
            status=AcknowledgementStatus.REJECTED,
            occurred_at=NOW,
        )


def test_irrigation_delta_and_outcome_must_be_consistent() -> None:
    with pytest.raises(ValueError, match="result must be increased"):
        IrrigationResult(
            event_id=MESSAGE_ID,
            farm_id=FARM_ID,
            device_id=DEVICE_ID,
            soil_moisture_before=40.0,
            soil_moisture_after=50.0,
            delta=10.0,
            result=IrrigationOutcome.UNCHANGED,
            completed_at=NOW,
        )


@pytest.mark.parametrize(
    ("schema_name", "instance"),
    [
        (
            "telemetry.schema.json",
            Telemetry(
                message_id=MESSAGE_ID,
                farm_id=FARM_ID,
                device_id=DEVICE_ID,
                metric=TelemetryMetric.SOIL_MOISTURE,
                value=52.4,
                unit="%",
                recorded_at=NOW,
            ).to_dict(),
        ),
        ("pump-command.schema.json", _command_payload()),
        (
            "command-acknowledgement.schema.json",
            CommandAcknowledgement(
                acknowledgement_id=MESSAGE_ID,
                command_id=COMMAND_ID,
                farm_id=FARM_ID,
                device_id=DEVICE_ID,
                status=AcknowledgementStatus.COMPLETED,
                occurred_at=NOW,
                pump_state=False,
            ).to_dict(),
        ),
        (
            "command-acknowledgement.schema.json",
            CommandAcknowledgement(
                acknowledgement_id=MESSAGE_ID,
                command_id=COMMAND_ID,
                farm_id=FARM_ID,
                device_id=DEVICE_ID,
                status=AcknowledgementStatus.REJECTED,
                occurred_at=NOW,
                reason_code="invalid_command",
            ).to_dict(),
        ),
        (
            "device-status.schema.json",
            DeviceStatus(
                message_id=MESSAGE_ID,
                farm_id=FARM_ID,
                device_id=DEVICE_ID,
                online=False,
                pump_state=False,
                health=DeviceHealth.DEGRADED,
                recorded_at=NOW,
                uptime_seconds=0,
                firmware_version="0.1.0",
                errors=("connection_lost",),
            ).to_dict(),
        ),
        (
            "irrigation-result.schema.json",
            IrrigationResult(
                event_id=MESSAGE_ID,
                farm_id=FARM_ID,
                device_id=DEVICE_ID,
                soil_moisture_before=50.0,
                soil_moisture_after=50.0,
                delta=0.0,
                result=IrrigationOutcome.UNCHANGED,
                completed_at=NOW,
            ).to_dict(),
        ),
    ],
)
def test_python_output_conforms_to_language_neutral_json_schema(
    schema_name: str, instance: dict[str, object]
) -> None:
    schema = json.loads((CONTRACT_ROOT / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)
