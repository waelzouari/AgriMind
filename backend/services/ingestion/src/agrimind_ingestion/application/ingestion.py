"""Authorize and persist canonical telemetry and device status messages."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from agrimind_ingestion.application.ports import DeviceRegistryPort, TrustedIngestionPort
from agrimind_ingestion.contracts import ContractValidator, ContractViolation, parse_topic
from agrimind_ingestion.domain import (
    IngestionOutcome,
    IngestionResult,
    MessageKind,
    PersistenceRejected,
    PersistenceUnavailable,
)


class IngestionService:
    def __init__(
        self,
        contracts: ContractValidator,
        registry: DeviceRegistryPort,
        persistence: TrustedIngestionPort,
        *,
        maximum_age: timedelta = timedelta(hours=24),
        maximum_future_skew: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._contracts = contracts
        self._registry = registry
        self._persistence = persistence
        self._maximum_age = maximum_age
        self._maximum_future_skew = maximum_future_skew
        self._clock = clock or (lambda: datetime.now(UTC))
        self._logger = logger or logging.getLogger(__name__)

    def process(self, topic: str, payload: bytes, *, qos: int, retain: bool) -> IngestionResult:
        try:
            identity = parse_topic(topic)
            message = self._contracts.validate(identity, payload)
            if qos != 1:
                raise ContractViolation("invalid_qos")
            if identity.kind is MessageKind.TELEMETRY and retain:
                raise ContractViolation("retained_telemetry")
            now = self._now()
            if message.recorded_at < now - self._maximum_age:
                raise ContractViolation("stale_message")
            if message.recorded_at > now + self._maximum_future_skew:
                raise ContractViolation("future_message")

            registration = self._registry.get(identity.device_id)
            if registration is None:
                raise ContractViolation("unknown_device")
            if not registration.is_active:
                raise ContractViolation("inactive_device")
            if registration.farm_id != identity.farm_id:
                raise ContractViolation("device_farm_mismatch")

            if identity.kind is MessageKind.TELEMETRY:
                outcome = self._persistence.ingest_telemetry(message.payload)
            else:
                outcome = self._persistence.ingest_device_status(message.payload)
            result = IngestionResult(
                IngestionOutcome(outcome),
                outcome,
                message.message_id,
                identity.device_id,
                identity.farm_id,
                identity.kind,
            )
        except ContractViolation as error:
            result = IngestionResult(
                IngestionOutcome.REJECTED,
                error.reason_code,
                error.message_id or (message.message_id if "message" in locals() else None),
                error.device_id or (identity.device_id if "message" in locals() else None),
                error.farm_id or (identity.farm_id if "message" in locals() else None),
                error.kind or (identity.kind if "message" in locals() else None),
            )
        except PersistenceRejected as error:
            result = IngestionResult(
                IngestionOutcome.REJECTED,
                error.reason_code,
                message.message_id if "message" in locals() else None,
                identity.device_id if "identity" in locals() else None,
                identity.farm_id if "identity" in locals() else None,
                identity.kind if "identity" in locals() else None,
            )
        except PersistenceUnavailable:
            result = IngestionResult(IngestionOutcome.RETRYABLE, "persistence_unavailable")

        self._logger.info(
            "ingestion_result",
            extra={
                "event": "ingestion_result",
                "outcome": result.outcome.value,
                "reason_code": result.reason_code,
                "message_id": str(result.message_id) if result.message_id else None,
                "device_id": str(result.device_id) if result.device_id else None,
            },
        )
        return result

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise ValueError("ingestion clock must return UTC")
        return now
