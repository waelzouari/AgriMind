"""Mockable authentication, authorization, image and model boundaries."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from agrimind_cv_inference.domain.models import (
    AuthenticatedUser,
    ModelResult,
    ValidatedImage,
)


class AuthenticationPort(Protocol):
    def authenticate(self, access_token: str) -> AuthenticatedUser: ...


class FarmAuthorizationPort(Protocol):
    def is_member(self, user: AuthenticatedUser, farm_id: UUID, access_token: str) -> bool: ...


class ImageValidationPort(Protocol):
    def validate(self, body: bytes, content_type: str) -> ValidatedImage: ...


class ModelInferencePort(Protocol):
    def predict(self, image: ValidatedImage) -> ModelResult: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdentifierFactory(Protocol):
    def new(self) -> UUID: ...
