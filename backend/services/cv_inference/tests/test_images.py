from __future__ import annotations

import io

import pytest
from PIL import Image

from agrimind_cv_inference.adapters.images import MAX_BODY_BYTES, PillowImageValidator
from agrimind_cv_inference.domain.models import ServiceError


def encoded(format_name: str, mode: str = "RGB", size: tuple[int, int] = (16, 12)) -> bytes:
    stream = io.BytesIO()
    color: int | tuple[int, ...] = (
        120 if mode == "L" else ((1, 2, 3, 4) if mode == "RGBA" else (1, 2, 3))
    )
    Image.new(mode, size, color).save(stream, format=format_name)
    return stream.getvalue()


@pytest.mark.parametrize(("mime", "format_name"), [("image/jpeg", "JPEG"), ("image/png", "PNG")])
def test_valid_jpeg_and_png(mime: str, format_name: str) -> None:
    result = PillowImageValidator().validate(encoded(format_name), mime)
    assert (result.width, result.height, result.rgb_image.mode) == (16, 12, "RGB")  # type: ignore[attr-defined]


@pytest.mark.parametrize("mode", ["L", "RGBA"])
def test_grayscale_and_rgba_follow_rgb_contract(mode: str) -> None:
    result = PillowImageValidator().validate(encoded("PNG", mode), "image/png")
    assert result.rgb_image.mode == "RGB"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("body", "mime", "code"),
    [
        (b"", "image/png", "invalid_image"),
        (b"not an image", "image/png", "invalid_image"),
        (encoded("PNG"), "image/jpeg", "unsupported_image_type"),
        (encoded("PNG")[:30], "image/png", "invalid_image"),
        (encoded("PNG"), "image/gif", "unsupported_image_type"),
    ],
)
def test_invalid_images_fail_safely(body: bytes, mime: str, code: str) -> None:
    with pytest.raises(ServiceError) as caught:
        PillowImageValidator().validate(body, mime)
    assert caught.value.code == code
    assert repr(body) not in str(caught.value)


def test_encoded_size_limit_is_applied_before_decode() -> None:
    with pytest.raises(ServiceError) as caught:
        PillowImageValidator().validate(b"x" * (MAX_BODY_BYTES + 1), "image/png")
    assert caught.value.code == "image_too_large"


def test_dimension_and_pixel_limits() -> None:
    with pytest.raises(ServiceError) as width:
        PillowImageValidator().validate(encoded("PNG", size=(4097, 1)), "image/png")
    assert width.value.code == "unsupported_image_dimensions"
    with pytest.raises(ServiceError) as pixels:
        PillowImageValidator().validate(encoded("PNG", size=(4096, 3907)), "image/png")
    assert pixels.value.code == "unsupported_image_dimensions"


def test_decompression_bomb_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)
    with pytest.raises(ServiceError) as caught:
        PillowImageValidator().validate(encoded("PNG", size=(3, 3)), "image/png")
    assert caught.value.code == "unsupported_image_dimensions"


def test_animated_png_is_rejected() -> None:
    stream = io.BytesIO()
    frames = [Image.new("RGB", (2, 2), color) for color in ("red", "blue")]
    frames[0].save(stream, format="PNG", save_all=True, append_images=frames[1:])
    with pytest.raises(ServiceError) as caught:
        PillowImageValidator().validate(stream.getvalue(), "image/png")
    assert caught.value.code == "invalid_image"
