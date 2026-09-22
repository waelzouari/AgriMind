"""Shared validation and canonical JSON helpers for v1 contracts."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypeVar
from uuid import UUID

SCHEMA_VERSION = 1
TOPIC_VERSION = "v1"


def require_exact_fields(
    data: Mapping[str, object], *, required: set[str], optional: set[str] | None = None
) -> None:
    optional = optional or set()
    missing = required - data.keys()
    unknown = data.keys() - required - optional
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")


def require_schema_version(value: object) -> int:
    if type(value) is not int or value != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    return value


def parse_uuid(value: object, field: str) -> UUID:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical UUID string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{field} must be a canonical UUID string") from error
    if parsed.int == 0 or str(parsed) != value:
        raise ValueError(f"{field} must be a non-zero canonical UUID string")
    return parsed


def parse_utc_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} must be a valid RFC 3339 timestamp") from error
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must use UTC")
    return parsed


def format_utc_timestamp(value: datetime, field: str) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be timezone-aware UTC")
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite")
    return converted


def non_negative_integer(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


EnumT = TypeVar("EnumT", bound=StrEnum)


def enum_value(enum_type: type[EnumT], value: object, field: str) -> EnumT:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"unsupported {field}: {value}") from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_json(payload: str | bytes) -> dict[str, object]:
    try:
        value: Any = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("payload must be valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError("payload must be a JSON object")
    return {str(key): item for key, item in value.items()}


def encode_json(data: Mapping[str, object]) -> str:
    """Serialize deterministically with no Python-specific representations."""

    return json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
