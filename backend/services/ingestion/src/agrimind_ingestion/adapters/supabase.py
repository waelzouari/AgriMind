"""Minimal Supabase REST adapter confined to the trusted server runtime."""

from __future__ import annotations

import json
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from agrimind_ingestion.application.ports import DeviceRegistryPort, TrustedIngestionPort
from agrimind_ingestion.domain import (
    DeviceRegistration,
    PersistenceRejected,
    PersistenceUnavailable,
)


class RestClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any: ...


class SupabaseRestClient:
    def __init__(self, url: str, service_role_key: str, *, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Supabase timeout must be positive")
        self._url = url.rstrip("/")
        self._key = service_role_key
        self._timeout_seconds = timeout_seconds

    def __repr__(self) -> str:
        return f"SupabaseRestClient(url={self._url!r}, service_role_key=*** )"

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        if prefer is not None:
            headers["Prefer"] = prefer
        request = Request(
            f"{self._url}/rest/v1/{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                content = response.read()
        except HTTPError as error:
            content = error.read()
            message = self._safe_error_message(content)
            if 400 <= error.code < 500:
                raise PersistenceRejected(message) from error
            raise PersistenceUnavailable("Supabase request failed") from error
        except (URLError, TimeoutError, OSError) as error:
            raise PersistenceUnavailable("Supabase request unavailable") from error
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise PersistenceUnavailable("Supabase returned invalid JSON") from error

    @staticmethod
    def _safe_error_message(content: bytes) -> str:
        try:
            decoded = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "persistence_rejected"
        message = decoded.get("message") if isinstance(decoded, dict) else None
        allowed = {
            "unknown_device",
            "inactive_device",
            "device_farm_mismatch",
            "message_id_conflict",
        }
        return message if message in allowed else "persistence_rejected"


class SupabaseRegistryRepository(DeviceRegistryPort):
    def __init__(self, client: RestClient) -> None:
        self._client = client

    def get(self, device_id: UUID) -> DeviceRegistration | None:
        rows = self._client.request(
            "GET",
            "devices?"
            + urlencode({"id": f"eq.{device_id}", "select": "id,farm_id,label,is_active"}),
        )
        if not rows:
            return None
        return self._registration(rows[0])

    def farm_exists(self, farm_id: UUID) -> bool:
        rows = self._client.request(
            "GET",
            "farms?" + urlencode({"id": f"eq.{farm_id}", "select": "id"}),
        )
        return bool(rows)

    def create(self, registration: DeviceRegistration) -> DeviceRegistration:
        rows = self._client.request(
            "POST",
            "devices?select=id,farm_id,label,is_active",
            body={
                "id": str(registration.device_id),
                "farm_id": str(registration.farm_id),
                "label": registration.label,
                "is_active": registration.is_active,
            },
            prefer="return=representation",
        )
        if not rows:
            raise PersistenceUnavailable("device creation returned no representation")
        return self._registration(rows[0])

    def update(
        self,
        device_id: UUID,
        *,
        is_active: bool | None = None,
        label: str | None = None,
        update_label: bool = False,
    ) -> DeviceRegistration:
        changes: dict[str, Any] = {}
        if is_active is not None:
            changes["is_active"] = is_active
        if update_label:
            changes["label"] = label
        rows = self._client.request(
            "PATCH",
            "devices?"
            + urlencode({"id": f"eq.{device_id}", "select": "id,farm_id,label,is_active"}),
            body=changes,
            prefer="return=representation",
        )
        if not rows:
            raise PersistenceRejected("unknown_device")
        return self._registration(rows[0])

    @staticmethod
    def _registration(row: dict[str, Any]) -> DeviceRegistration:
        return DeviceRegistration(
            UUID(row["id"]),
            UUID(row["farm_id"]),
            row.get("label"),
            bool(row["is_active"]),
        )


class SupabaseIngestionRepository(TrustedIngestionPort):
    def __init__(self, client: RestClient) -> None:
        self._client = client

    def ingest_telemetry(self, payload: dict[str, Any]) -> str:
        return self._rpc(
            "ingest_telemetry",
            {
                "incoming_message_id": payload["message_id"],
                "incoming_farm_id": payload["farm_id"],
                "incoming_device_id": payload["device_id"],
                "incoming_schema_version": payload["schema_version"],
                "incoming_metric": payload["metric"],
                "incoming_value": payload["value"],
                "incoming_unit": payload["unit"],
                "incoming_quality": payload["quality"],
                "incoming_recorded_at": payload["recorded_at"],
            },
        )

    def ingest_device_status(self, payload: dict[str, Any]) -> str:
        return self._rpc(
            "ingest_device_status",
            {
                "incoming_message_id": payload["message_id"],
                "incoming_farm_id": payload["farm_id"],
                "incoming_device_id": payload["device_id"],
                "incoming_schema_version": payload["schema_version"],
                "incoming_online": payload["online"],
                "incoming_pump_state": payload["pump_state"],
                "incoming_health": payload["health"],
                "incoming_recorded_at": payload["recorded_at"],
                "incoming_uptime_seconds": payload["uptime_seconds"],
                "incoming_firmware_version": payload["firmware_version"],
                "incoming_errors": payload["errors"],
            },
        )

    def _rpc(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._client.request("POST", f"rpc/{name}", body=arguments)
        if result not in {"inserted", "duplicate"}:
            raise PersistenceUnavailable("unexpected ingestion RPC result")
        return cast(str, result)
