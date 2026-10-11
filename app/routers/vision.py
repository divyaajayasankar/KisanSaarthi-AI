from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.image_quality_service import (
    ImageValidationError,
    validate_image,
)


router = APIRouter(
    prefix="/api/vision",
    tags=["vision"],
)


@router.post("/upload")
async def upload_image(
    image: UploadFile = File(...),
):
    """
    Phase 1 image-upload endpoint.

    This endpoint:
    - accepts farmer images
    - validates size
    - validates MIME type
    - validates actual image format
    - rejects corrupt images
    - returns image metadata

    No disease prediction is performed yet.
    """

    try:
        image_bytes = await image.read()

        result = validate_image(
            filename=image.filename or "uploaded_image",
            content_type=image.content_type or "",
            image_bytes=image_bytes,
        )

        return {
            "status": "valid",
            "filename": result.filename,
            "content_type": result.content_type,
            "image_format": result.image_format,
            "width": result.width,
            "height": result.height,
            "size_bytes": result.size_bytes,
            "message": "Image accepted for visual analysis.",
        }

    except ImageValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:
        await image.close()