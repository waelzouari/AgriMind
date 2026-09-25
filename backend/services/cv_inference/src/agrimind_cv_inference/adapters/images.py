"""Bounded Pillow image decoding with real format validation."""

from __future__ import annotations

import io
import warnings

from PIL import Image, UnidentifiedImageError

from agrimind_cv_inference.domain.models import ServiceError, ValidatedImage

MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_WIDTH = 4096
MAX_HEIGHT = 4096
MAX_PIXELS = 16_000_000
ALLOWED = {"image/jpeg": "JPEG", "image/png": "PNG"}


class PillowImageValidator:
    def validate(self, body: bytes, content_type: str) -> ValidatedImage:
        normalized = content_type.split(";", 1)[0].strip().lower()
        if normalized not in ALLOWED:
            raise ServiceError("unsupported_image_type", "Only JPEG and PNG are supported")
        if not body:
            raise ServiceError("invalid_image", "Image is empty")
        if len(body) > MAX_BODY_BYTES:
            raise ServiceError("image_too_large", "Image exceeds the encoded size limit")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(body)) as opened:
                    opened.verify()
                with Image.open(io.BytesIO(body)) as opened:
                    if opened.format != ALLOWED[normalized]:
                        raise ServiceError(
                            "unsupported_image_type", "Image content does not match its MIME type"
                        )
                    if getattr(opened, "n_frames", 1) != 1:
                        raise ServiceError(
                            "invalid_image", "Animated or multipage images are unsupported"
                        )
                    width, height = opened.size
                    if width <= 0 or height <= 0:
                        raise ServiceError("invalid_image", "Image dimensions are invalid")
                    if width > MAX_WIDTH or height > MAX_HEIGHT or width * height > MAX_PIXELS:
                        raise ServiceError(
                            "unsupported_image_dimensions", "Image dimensions exceed safe limits"
                        )
                    opened.load()
                    rgb = opened.convert("RGB").copy()
        except ServiceError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ServiceError(
                "unsupported_image_dimensions", "Image dimensions exceed safe limits"
            ) from None
        except (OSError, UnidentifiedImageError, ValueError):
            raise ServiceError("invalid_image", "Image cannot be decoded") from None
        return ValidatedImage(normalized, width, height, rgb)
