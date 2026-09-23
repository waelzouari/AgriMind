"""Build minimal secret-safe telemetry persistence acknowledgements."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from agrimind_ingestion.domain import IngestionOutcome, IngestionResult

_REJECTION_REASONS = {
    "inactive_device": "inactive_device",
    "unknown_device": "unknown_device",
    "device_farm_mismatch": "farm_mismatch",
    "stale_message": "stale_message",
    "future_message": "future_message",
    "message_id_conflict": "message_id_conflict",
    "invalid_contract": "contract_invalid",
    "topic_payload_metric_mismatch": "contract_invalid",
    "invalid_qos": "contract_invalid",
    "retained_telemetry": "contract_invalid",
}


@dataclass(frozen=True, slots=True)
class IngestionAcknowledgementPublication:
    topic: str
    payload: str
    qos: int = 1
    retain: bool = False


class IngestionAcknowledgementFactory:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def create(self, result: IngestionResult) -> IngestionAcknowledgementPublication | None:
        if not result.terminal or not result.correlatable_telemetry:
            return None
        if result.outcome is IngestionOutcome.INSERTED:
            status, reason = "persisted", None
        elif result.outcome is IngestionOutcome.DUPLICATE:
            status, reason = "duplicate", None
        elif result.outcome is IngestionOutcome.REJECTED:
            reason = _REJECTION_REASONS.get(result.reason_code)
            if reason is None:
                return None
            status = "rejected"
        else:
            return None

        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("acknowledgement clock must return UTC")
        data: dict[str, object] = {
            "schema_version": 1,
            "message_id": str(result.message_id),
            "farm_id": str(result.farm_id),
            "device_id": str(result.device_id),
            "event_type": "telemetry",
            "status": status,
            "occurred_at": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }
        if reason is not None:
            data["reason_code"] = reason
        base = (f"agrimind/v1/farms/{result.farm_id}/devices/{result.device_id}").lower()
        return IngestionAcknowledgementPublication(
            f"{base}/sync/acks/{result.message_id}",
            json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
