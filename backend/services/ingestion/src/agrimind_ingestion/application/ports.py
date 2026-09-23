"""Infrastructure-neutral boundaries for registry and ingestion."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from agrimind_ingestion.domain import DeviceRegistration


class DeviceRegistryPort(Protocol):
    def get(self, device_id: UUID) -> DeviceRegistration | None: ...

    def create(self, registration: DeviceRegistration) -> DeviceRegistration: ...

    def update(
        self,
        device_id: UUID,
        *,
        is_active: bool | None = None,
        label: str | None = None,
        update_label: bool = False,
    ) -> DeviceRegistration: ...

    def farm_exists(self, farm_id: UUID) -> bool: ...


class TrustedIngestionPort(Protocol):
    def ingest_telemetry(self, payload: dict[str, Any]) -> str: ...

    def ingest_device_status(self, payload: dict[str, Any]) -> str: ...
