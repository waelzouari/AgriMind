from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest
from conftest import FARM, USER

from agrimind_cv_inference.adapters import supabase
from agrimind_cv_inference.adapters.supabase import SupabaseUserBoundary
from agrimind_cv_inference.domain.models import AuthenticatedUser, ServiceError


class Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_user_validation_and_rls_membership_use_user_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[object] = []

    def request(value: object, *, timeout: float) -> Response:
        del timeout
        requests.append(value)
        return Response({"id": str(USER)} if len(requests) == 1 else [{"farm_id": str(FARM)}])

    monkeypatch.setattr(supabase, "urlopen", request)
    boundary = SupabaseUserBoundary("https://example.supabase.co", "public-key")
    user = boundary.authenticate("user-token")
    assert user == AuthenticatedUser(USER)
    assert boundary.is_member(user, FARM, "user-token")
    assert all(item.headers["Authorization"] == "Bearer user-token" for item in requests)  # type: ignore[attr-defined]
    assert "public-key" not in repr(boundary)


def test_invalid_or_expired_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def rejected(value: object, *, timeout: float) -> Response:
        del value, timeout
        raise HTTPError("url", 401, "unauthorized", {}, io.BytesIO())

    monkeypatch.setattr(supabase, "urlopen", rejected)
    with pytest.raises(ServiceError) as caught:
        SupabaseUserBoundary("https://example.supabase.co", "public-key").authenticate("expired")
    assert caught.value.code == "invalid_token"
