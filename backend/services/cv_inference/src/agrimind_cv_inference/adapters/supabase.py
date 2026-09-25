"""Supabase Auth and user-JWT RLS membership adapters without privileged keys."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from agrimind_cv_inference.domain.models import AuthenticatedUser, ServiceError


class SupabaseUserBoundary:
    def __init__(self, url: str, publishable_key: str, *, timeout_seconds: float = 10) -> None:
        self._url = url.rstrip("/")
        self._key = publishable_key
        self._timeout = timeout_seconds

    def __repr__(self) -> str:
        return f"SupabaseUserBoundary(url={self._url!r}, publishable_key=***)"

    def authenticate(self, access_token: str) -> AuthenticatedUser:
        request = Request(
            f"{self._url}/auth/v1/user",
            headers={"apikey": self._key, "Authorization": f"Bearer {access_token}"},
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read())
            return AuthenticatedUser(UUID(payload["id"]))
        except HTTPError as error:
            if error.code in {400, 401, 403}:
                raise ServiceError("invalid_token", "Authentication failed") from error
            raise ServiceError("invalid_token", "Authentication is unavailable") from error
        except (
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            raise ServiceError("invalid_token", "Authentication failed") from error

    def is_member(self, user: AuthenticatedUser, farm_id: UUID, access_token: str) -> bool:
        query = urlencode(
            {
                "farm_id": f"eq.{farm_id}",
                "user_id": f"eq.{user.user_id}",
                "select": "farm_id",
                "limit": "1",
            }
        )
        request = Request(
            f"{self._url}/rest/v1/farm_memberships?{query}",
            headers={
                "apikey": self._key,
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read())
            return isinstance(payload, list) and len(payload) == 1
        except HTTPError as error:
            if error.code in {401, 403, 404}:
                return False
            raise ServiceError("farm_access_denied", "Farm is unavailable") from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ServiceError("farm_access_denied", "Farm is unavailable") from error
