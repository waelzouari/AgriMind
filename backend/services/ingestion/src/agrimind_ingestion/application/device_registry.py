"""Trusted device provisioning without exposing a client-facing API."""

from __future__ import annotations

from uuid import UUID

from agrimind_ingestion.application.ports import DeviceRegistryPort
from agrimind_ingestion.domain import (
    DeviceRegistration,
    RegistrationOutcome,
    RegistrationResult,
    RegistryConflict,
)


def _validate_uuid(value: UUID, field: str) -> None:
    if value.int == 0:
        raise ValueError(f"{field} must be non-zero")


def _validate_label(label: str | None) -> str | None:
    if label is None:
        return None
    normalized = label.strip()
    if not normalized:
        raise ValueError("label must not be blank")
    return normalized


class DeviceRegistryService:
    def __init__(self, registry: DeviceRegistryPort) -> None:
        self._registry = registry

    def register(
        self,
        device_id: UUID,
        farm_id: UUID,
        *,
        label: str | None = None,
        is_active: bool = True,
    ) -> RegistrationResult:
        _validate_uuid(device_id, "device_id")
        _validate_uuid(farm_id, "farm_id")
        normalized_label = _validate_label(label)
        existing = self._registry.get(device_id)
        if existing is not None:
            if existing.farm_id != farm_id:
                raise RegistryConflict("device is already registered to another farm")
            return RegistrationResult(RegistrationOutcome.EXISTING, existing)
        if not self._registry.farm_exists(farm_id):
            raise ValueError("farm does not exist")
        registration = DeviceRegistration(device_id, farm_id, normalized_label, is_active)
        return RegistrationResult(
            RegistrationOutcome.CREATED,
            self._registry.create(registration),
        )

    def get(self, device_id: UUID) -> DeviceRegistration | None:
        _validate_uuid(device_id, "device_id")
        return self._registry.get(device_id)

    def activate(self, device_id: UUID) -> RegistrationResult:
        return self._set_active(device_id, True)

    def deactivate(self, device_id: UUID) -> RegistrationResult:
        return self._set_active(device_id, False)

    def update_label(self, device_id: UUID, label: str | None) -> RegistrationResult:
        _validate_uuid(device_id, "device_id")
        existing = self._require(device_id)
        updated = self._registry.update(
            existing.device_id,
            label=_validate_label(label),
            update_label=True,
        )
        return RegistrationResult(RegistrationOutcome.UPDATED, updated)

    def _set_active(self, device_id: UUID, is_active: bool) -> RegistrationResult:
        _validate_uuid(device_id, "device_id")
        existing = self._require(device_id)
        if existing.is_active is is_active:
            return RegistrationResult(RegistrationOutcome.EXISTING, existing)
        updated = self._registry.update(existing.device_id, is_active=is_active)
        return RegistrationResult(RegistrationOutcome.UPDATED, updated)

    def _require(self, device_id: UUID) -> DeviceRegistration:
        registration = self._registry.get(device_id)
        if registration is None:
            raise ValueError("device does not exist")
        return registration
