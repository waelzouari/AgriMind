from uuid import UUID

import pytest
from fakes import FakeRegistry

from agrimind_ingestion.application.device_registry import DeviceRegistryService
from agrimind_ingestion.domain import RegistrationOutcome, RegistryConflict

FARM_A = UUID("11111111-1111-4111-8111-111111111111")
FARM_B = UUID("99999999-9999-4999-8999-999999999999")
DEVICE = UUID("22222222-2222-4222-8222-222222222222")


def test_register_repeat_activation_and_deactivation() -> None:
    registry = FakeRegistry({FARM_A})
    service = DeviceRegistryService(registry)

    created = service.register(DEVICE, FARM_A, label=" Edge 1 ")
    repeated = service.register(DEVICE, FARM_A, label="ignored")
    deactivated = service.deactivate(DEVICE)
    activated = service.activate(DEVICE)
    renamed = service.update_label(DEVICE, "North edge")

    assert created.outcome is RegistrationOutcome.CREATED
    assert created.registration.label == "Edge 1"
    assert repeated.outcome is RegistrationOutcome.EXISTING
    assert deactivated.registration.is_active is False
    assert activated.registration.is_active is True
    assert renamed.registration.label == "North edge"


def test_registration_rejects_missing_farm_cross_farm_and_zero_uuid() -> None:
    registry = FakeRegistry({FARM_A})
    service = DeviceRegistryService(registry)
    service.register(DEVICE, FARM_A)

    with pytest.raises(RegistryConflict):
        service.register(DEVICE, FARM_B)
    with pytest.raises(ValueError, match="farm does not exist"):
        service.register(UUID(int=3), FARM_B)
    with pytest.raises(ValueError, match="non-zero"):
        service.register(UUID(int=0), FARM_A)
