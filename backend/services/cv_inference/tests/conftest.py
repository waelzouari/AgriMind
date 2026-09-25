from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from agrimind_cv_inference.adapters.images import PillowImageValidator
from agrimind_cv_inference.application.service import InferenceService
from agrimind_cv_inference.domain.models import (
    AuthenticatedUser,
    Classification,
    ModelResult,
    ServiceError,
    ValidatedImage,
)

FARM = UUID("31313131-3131-4131-8131-313131313131")
OTHER_FARM = UUID("31313131-3131-4131-8131-313131313132")
USER = UUID("31313131-3131-4131-8131-313131313133")
IDENTIFIER = UUID("31313131-3131-4131-8131-313131313134")
NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)


class FakeAuth:
    def authenticate(self, access_token: str) -> AuthenticatedUser:
        if access_token != "valid-token":
            raise ServiceError("invalid_token", "Authentication failed")
        return AuthenticatedUser(USER)


class FakeAuthorization:
    def is_member(self, user: AuthenticatedUser, farm_id: UUID, access_token: str) -> bool:
        return user.user_id == USER and farm_id == FARM and access_token == "valid-token"


class FakeModel:
    error: Exception | None = None
    classification = Classification.ANOMALY
    score = 0.8

    def predict(self, image: ValidatedImage) -> ModelResult:
        del image
        if self.error:
            raise self.error
        return ModelResult(
            self.classification,
            self.score,
            0.6,
            "1.0.0",
            "agrimind-cv-mobilenet-v2-preprocessing-v1",
            "a" * 64,
            "d" * 64,
        )


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FixedIdentifiers:
    def new(self) -> UUID:
        return IDENTIFIER


@pytest.fixture
def model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def service(model: FakeModel) -> InferenceService:
    return InferenceService(
        FakeAuth(),
        FakeAuthorization(),
        PillowImageValidator(),
        model,
        FixedClock(),
        FixedIdentifiers(),
    )
