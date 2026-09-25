"""Validation of the existing language-neutral v1 contracts and topics."""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from agrimind_ingestion.domain import MessageKind, TopicIdentity, ValidatedMessage

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
_TOPIC = re.compile(
    rf"^agrimind/v1/farms/(?P<farm>{_UUID})/devices/(?P<device>{_UUID})/"
    rf"(?:(?:telemetry/(?P<metric>soil_moisture|temperature|humidity|tank_level))|"
    rf"(?P<status>status/device)|acks/(?P<command>{_UUID})|"
    rf"(?P<irrigation>events/irrigation_result))$"
)
# A maximal canonical v1 device status is 1,471 bytes. Four KiB leaves generous
# headroom for every current contract while rejecting abusive input before decoding.
MAX_INBOUND_MQTT_PAYLOAD_BYTES = 4_096


class ContractViolation(ValueError):
    def __init__(
        self,
        reason_code: str,
        *,
        message_id: UUID | None = None,
        farm_id: UUID | None = None,
        device_id: UUID | None = None,
        kind: MessageKind | None = None,
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.message_id = message_id
        self.farm_id = farm_id
        self.device_id = device_id
        self.kind = kind


def _reject_duplicate_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _canonical_uuid(value: object, field: str) -> UUID:
    if not isinstance(value, str):
        raise ContractViolation(f"invalid_{field}")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ContractViolation(f"invalid_{field}") from error
    if parsed.int == 0 or str(parsed) != value:
        raise ContractViolation(f"invalid_{field}")
    return parsed


def _utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractViolation("invalid_recorded_at")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ContractViolation("invalid_recorded_at") from error
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ContractViolation("invalid_recorded_at")
    return parsed


def parse_topic(topic: str) -> TopicIdentity:
    match = _TOPIC.fullmatch(topic)
    if match is None:
        raise ContractViolation("invalid_topic")
    metric = match.group("metric")
    if metric:
        kind = MessageKind.TELEMETRY
    elif match.group("status"):
        kind = MessageKind.DEVICE_STATUS
    elif match.group("command"):
        kind = MessageKind.COMMAND_ACKNOWLEDGEMENT
    else:
        kind = MessageKind.IRRIGATION_RESULT
    return TopicIdentity(
        kind=kind,
        farm_id=_canonical_uuid(match.group("farm"), "farm_id"),
        device_id=_canonical_uuid(match.group("device"), "device_id"),
        metric=metric,
        command_id=(
            _canonical_uuid(match.group("command"), "command_id")
            if match.group("command")
            else None
        ),
    )


class ContractValidator:
    def __init__(self, contract_root: Path) -> None:
        self._validators = {
            MessageKind.TELEMETRY: self._load(contract_root / "telemetry.schema.json"),
            MessageKind.DEVICE_STATUS: self._load(contract_root / "device-status.schema.json"),
            MessageKind.COMMAND_ACKNOWLEDGEMENT: self._load(
                contract_root / "command-acknowledgement.schema.json"
            ),
            MessageKind.IRRIGATION_RESULT: self._load(
                contract_root / "irrigation-result.schema.json"
            ),
        }

    @staticmethod
    def _load(path: Path) -> Draft202012Validator:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, identity: TopicIdentity, payload: bytes) -> ValidatedMessage:
        if len(payload) > MAX_INBOUND_MQTT_PAYLOAD_BYTES:
            raise ContractViolation("payload_too_large")
        try:
            decoded = payload.decode("utf-8")
            data = json.loads(
                decoded,
                object_pairs_hook=_reject_duplicate_fields,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"invalid JSON constant: {value}")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise ContractViolation("malformed_json") from error
        if not isinstance(data, dict):
            raise ContractViolation("invalid_contract")
        candidate_message_id: UUID | None = None
        candidate_farm_id: UUID | None = None
        candidate_device_id: UUID | None = None
        try:
            identity_field = self._identity_field(identity.kind)
            candidate_message_id = _canonical_uuid(data.get(identity_field), identity_field)
            candidate_farm_id = _canonical_uuid(data.get("farm_id"), "farm_id")
            candidate_device_id = _canonical_uuid(data.get("device_id"), "device_id")
            if candidate_farm_id != identity.farm_id or candidate_device_id != identity.device_id:
                candidate_message_id = None
                candidate_farm_id = None
                candidate_device_id = None
        except ContractViolation:
            pass
        try:
            self._validators[identity.kind].validate(data)
        except ValidationError as error:
            raise ContractViolation(
                "invalid_contract",
                message_id=candidate_message_id,
                farm_id=candidate_farm_id,
                device_id=candidate_device_id,
                kind=identity.kind if candidate_message_id is not None else None,
            ) from error

        identity_field = self._identity_field(identity.kind)
        message_id = _canonical_uuid(data.get(identity_field), identity_field)
        farm_id = _canonical_uuid(data.get("farm_id"), "farm_id")
        device_id = _canonical_uuid(data.get("device_id"), "device_id")
        if farm_id != identity.farm_id:
            raise ContractViolation("topic_payload_farm_mismatch")
        if device_id != identity.device_id:
            raise ContractViolation("topic_payload_device_mismatch")
        if identity.kind is MessageKind.TELEMETRY and data.get("metric") != identity.metric:
            raise ContractViolation(
                "topic_payload_metric_mismatch",
                message_id=message_id,
                farm_id=farm_id,
                device_id=device_id,
                kind=identity.kind,
            )
        if (
            identity.kind is MessageKind.COMMAND_ACKNOWLEDGEMENT
            and _canonical_uuid(data.get("command_id"), "command_id") != identity.command_id
        ):
            raise ContractViolation(
                "topic_payload_command_mismatch",
                message_id=message_id,
                farm_id=farm_id,
                device_id=device_id,
                kind=identity.kind,
            )
        if identity.kind is MessageKind.IRRIGATION_RESULT:
            self._validate_irrigation_result(data, message_id, farm_id, device_id)
        return ValidatedMessage(
            identity=identity,
            message_id=message_id,
            recorded_at=_utc_timestamp(data.get(self._timestamp_field(identity.kind))),
            payload=data,
        )

    @staticmethod
    def _identity_field(kind: MessageKind) -> str:
        if kind is MessageKind.COMMAND_ACKNOWLEDGEMENT:
            return "acknowledgement_id"
        if kind is MessageKind.IRRIGATION_RESULT:
            return "event_id"
        return "message_id"

    @staticmethod
    def _timestamp_field(kind: MessageKind) -> str:
        if kind is MessageKind.COMMAND_ACKNOWLEDGEMENT:
            return "occurred_at"
        if kind is MessageKind.IRRIGATION_RESULT:
            return "completed_at"
        return "recorded_at"

    @staticmethod
    def _validate_irrigation_result(
        data: dict[str, object],
        message_id: UUID,
        farm_id: UUID,
        device_id: UUID,
    ) -> None:
        before = data["soil_moisture_before"]
        after = data["soil_moisture_after"]
        delta = data["delta"]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in (before, after, delta)
        ):
            raise ContractViolation("invalid_contract")
        before_number = float(cast(int | float, before))
        after_number = float(cast(int | float, after))
        delta_number = float(cast(int | float, delta))
        expected_delta = round(after_number - before_number, 1)
        expected_result = (
            "increased"
            if expected_delta > 0
            else "decreased"
            if expected_delta < 0
            else "unchanged"
        )
        if abs(delta_number - expected_delta) > 0.001 or data["result"] != expected_result:
            raise ContractViolation(
                "invalid_contract",
                message_id=message_id,
                farm_id=farm_id,
                device_id=device_id,
                kind=MessageKind.IRRIGATION_RESULT,
            )
