"""Validation of the existing language-neutral v1 contracts and topics."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from agrimind_ingestion.domain import MessageKind, TopicIdentity, ValidatedMessage

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
_TOPIC = re.compile(
    rf"^agrimind/v1/farms/(?P<farm>{_UUID})/devices/(?P<device>{_UUID})/"
    rf"(?:(?:telemetry/(?P<metric>soil_moisture|temperature|humidity|tank_level))|"
    rf"(?P<status>status/device))$"
)


class ContractViolation(ValueError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


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
    kind = MessageKind.TELEMETRY if metric else MessageKind.DEVICE_STATUS
    return TopicIdentity(
        kind=kind,
        farm_id=_canonical_uuid(match.group("farm"), "farm_id"),
        device_id=_canonical_uuid(match.group("device"), "device_id"),
        metric=metric,
    )


class ContractValidator:
    def __init__(self, contract_root: Path) -> None:
        self._validators = {
            MessageKind.TELEMETRY: self._load(contract_root / "telemetry.schema.json"),
            MessageKind.DEVICE_STATUS: self._load(contract_root / "device-status.schema.json"),
        }

    @staticmethod
    def _load(path: Path) -> Draft202012Validator:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, identity: TopicIdentity, payload: bytes) -> ValidatedMessage:
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
        try:
            self._validators[identity.kind].validate(data)
        except ValidationError as error:
            raise ContractViolation("invalid_contract") from error

        message_id = _canonical_uuid(data.get("message_id"), "message_id")
        farm_id = _canonical_uuid(data.get("farm_id"), "farm_id")
        device_id = _canonical_uuid(data.get("device_id"), "device_id")
        if farm_id != identity.farm_id:
            raise ContractViolation("topic_payload_farm_mismatch")
        if device_id != identity.device_id:
            raise ContractViolation("topic_payload_device_mismatch")
        if identity.kind is MessageKind.TELEMETRY and data.get("metric") != identity.metric:
            raise ContractViolation("topic_payload_metric_mismatch")
        return ValidatedMessage(
            identity=identity,
            message_id=message_id,
            recorded_at=_utc_timestamp(data.get("recorded_at")),
            payload=data,
        )
