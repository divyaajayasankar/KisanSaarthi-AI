from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_IMAGE_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
}


class ImageValidationError(ValueError):
    """Raised when an uploaded image does not satisfy validation rules."""


@dataclass
class ImageValidationResult:
    filename: str
    content_type: str
    width: int
    height: int
    image_format: str
    size_bytes: int


def validate_image(
    *,
    filename: str,
    content_type: str,
    image_bytes: bytes,
) -> ImageValidationResult:

    if not image_bytes:
        raise ImageValidationError(
            "Uploaded image is empty."
        )

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ImageValidationError(
            f"Image exceeds maximum allowed size of "
            f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    normalized_content_type = (
        content_type or ""
    ).lower().strip()

    if normalized_content_type not in ALLOWED_MIME_TYPES:
        raise ImageValidationError(
            "Unsupported image MIME type. "
            "Allowed types are JPEG, PNG, and WEBP."
        )

    try:
        image_stream = BytesIO(image_bytes)

        with Image.open(image_stream) as image:
            detected_format = (
                image.format or ""
            ).upper()

            if detected_format == "MPO":
                detected_format = "JPEG"

            if detected_format not in ALLOWED_IMAGE_FORMATS:
                raise ImageValidationError(
                    "Unsupported image format. "
                    "Allowed formats are JPEG, PNG, and WEBP."
                )

            width, height = image.size

            if width <= 0 or height <= 0:
                raise ImageValidationError(
                    "Image has invalid width or height."
                )

            image.verify()

    except ImageValidationError:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:

        raise ImageValidationError(
            "Uploaded file is not a valid or readable image."
        ) from exc

    expected_mime_by_format = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }

    expected_mime = (
        expected_mime_by_format[
            detected_format
        ]
    )

    if normalized_content_type != expected_mime:
        raise ImageValidationError(
            "Uploaded file MIME type does not match "
            "its actual image format."
        )

    return ImageValidationResult(
        filename=filename,
        content_type=normalized_content_type,
        width=width,
        height=height,
        image_format=detected_format,
        size_bytes=len(image_bytes),
    )
