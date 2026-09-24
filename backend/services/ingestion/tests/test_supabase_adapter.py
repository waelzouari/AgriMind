from __future__ import annotations

from typing import Any
from uuid import UUID

from agrimind_ingestion.adapters.supabase import (
    SupabaseIngestionRepository,
    SupabaseRegistryRepository,
    SupabaseRestClient,
)
from agrimind_ingestion.domain import DeviceRegistration

FARM = UUID("11111111-1111-4111-8111-111111111111")
DEVICE = UUID("22222222-2222-4222-8222-222222222222")


class FakeRestClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None, str | None]] = []
        self.response: Any = []

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        self.calls.append((method, path, body, prefer))
        return self.response


def test_registry_adapter_maps_existing_create_and_update() -> None:
    client = FakeRestClient()
    repository = SupabaseRegistryRepository(client)
    row = {"id": str(DEVICE), "farm_id": str(FARM), "label": "edge", "is_active": True}
    client.response = [row]

    assert repository.get(DEVICE) == DeviceRegistration(DEVICE, FARM, "edge", True)
    assert repository.farm_exists(FARM) is True
    assert repository.create(DeviceRegistration(DEVICE, FARM, "edge", True)).device_id == DEVICE
    assert repository.update(DEVICE, is_active=False).device_id == DEVICE

    assert [call[0] for call in client.calls] == ["GET", "GET", "POST", "PATCH"]


def test_ingestion_adapter_calls_only_the_restricted_rpcs() -> None:
    client = FakeRestClient()
    client.response = "inserted"
    repository = SupabaseIngestionRepository(client)
    telemetry = {
        "schema_version": 1,
        "message_id": str(UUID(int=3)),
        "farm_id": str(FARM),
        "device_id": str(DEVICE),
        "metric": "temperature",
        "value": 22,
        "unit": "°C",
        "quality": "valid",
        "recorded_at": "2026-09-23T12:00:00Z",
    }

    assert repository.ingest_telemetry(telemetry) == "inserted"
    assert client.calls[0][1] == "rpc/ingest_telemetry"

    acknowledgement = {
        "schema_version": 1,
        "acknowledgement_id": str(UUID(int=4)),
        "command_id": str(UUID(int=5)),
        "farm_id": str(FARM),
        "device_id": str(DEVICE),
        "status": "completed",
        "occurred_at": "2026-09-23T12:01:00Z",
        "pump_state": False,
    }
    result = {
        "schema_version": 1,
        "event_id": str(UUID(int=6)),
        "farm_id": str(FARM),
        "device_id": str(DEVICE),
        "soil_moisture_before": 40,
        "soil_moisture_after": 45,
        "delta": 5,
        "result": "increased",
        "completed_at": "2026-09-23T12:05:00Z",
    }
    assert repository.ingest_command_acknowledgement(acknowledgement) == "inserted"
    assert repository.ingest_irrigation_result(result) == "inserted"
    assert [call[1] for call in client.calls] == [
        "rpc/ingest_telemetry",
        "rpc/ingest_command_acknowledgement",
        "rpc/ingest_irrigation_result",
    ]


def test_supabase_client_repr_redacts_service_role() -> None:
    secret = "service-role-must-not-leak"  # pragma: allowlist secret
    client = SupabaseRestClient("https://example.supabase.co", secret)
    assert secret not in repr(client)
