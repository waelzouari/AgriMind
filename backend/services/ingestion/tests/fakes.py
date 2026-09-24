from __future__ import annotations

from typing import Any
from uuid import UUID

from agrimind_ingestion.domain import DeviceRegistration


class FakeRegistry:
    def __init__(self, farms: set[UUID] | None = None) -> None:
        self.farms = farms or set()
        self.devices: dict[UUID, DeviceRegistration] = {}

    def get(self, device_id: UUID) -> DeviceRegistration | None:
        return self.devices.get(device_id)

    def farm_exists(self, farm_id: UUID) -> bool:
        return farm_id in self.farms

    def create(self, registration: DeviceRegistration) -> DeviceRegistration:
        self.devices[registration.device_id] = registration
        return registration

    def update(
        self,
        device_id: UUID,
        *,
        is_active: bool | None = None,
        label: str | None = None,
        update_label: bool = False,
    ) -> DeviceRegistration:
        current = self.devices[device_id]
        updated = DeviceRegistration(
            device_id,
            current.farm_id,
            label if update_label else current.label,
            current.is_active if is_active is None else is_active,
        )
        self.devices[device_id] = updated
        return updated


class FakePersistence:
    def __init__(self) -> None:
        self.telemetry: list[dict[str, Any]] = []
        self.statuses: list[dict[str, Any]] = []
        self.acknowledgements: list[dict[str, Any]] = []
        self.irrigation_results: list[dict[str, Any]] = []
        self.failure: Exception | None = None
        self.outcome = "inserted"

    def ingest_telemetry(self, payload: dict[str, Any]) -> str:
        if self.failure:
            raise self.failure
        self.telemetry.append(payload)
        return self.outcome

    def ingest_device_status(self, payload: dict[str, Any]) -> str:
        if self.failure:
            raise self.failure
        self.statuses.append(payload)
        return self.outcome

    def ingest_command_acknowledgement(self, payload: dict[str, Any]) -> str:
        if self.failure:
            raise self.failure
        self.acknowledgements.append(payload)
        return self.outcome

    def ingest_irrigation_result(self, payload: dict[str, Any]) -> str:
        if self.failure:
            raise self.failure
        self.irrigation_results.append(payload)
        return self.outcome
