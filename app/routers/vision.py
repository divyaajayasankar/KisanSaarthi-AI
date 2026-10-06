from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.image_quality_service import (
    ImageValidationError,
    validate_image,
)
from app.services.vision_inference_service import (
    analyze_image,
    load_registry,
    supported_crops,
    torch_available,
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


@router.post("/analyze")
async def analyze(
    image: UploadFile = File(...),
    crop: str = Form(...),
):
    """Crop-aware disease analysis (separate from /upload, which is unchanged).

    Returns model_supported=false and decision=ABSTAIN for crops without a
    validated model; no visual diagnosis is claimed for them.
    """

    try:
        image_bytes = await image.read()
        validate_image(
            filename=image.filename or "uploaded_image",
            content_type=image.content_type or "",
            image_bytes=image_bytes,
        )
    except ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await image.close()

    result = analyze_image(crop, image_bytes)
    payload = result.as_dict()
    if not result.model_supported:
        payload["message"] = "Image diagnosis is not currently validated for this crop."
    return payload


@router.get("/models")
def models():
    """Which crops have a validated image model."""

    registry = load_registry().get("models", {})
    return {
        "runtime_available": torch_available(),
        "validated_crops": supported_crops(),
        "models": {
            crop: {
                "validated": entry.get("validated", False),
                "labels": entry.get("labels", []),
                "validation": entry.get("validation", {}),
            }
            for crop, entry in registry.items()
        },
    }
