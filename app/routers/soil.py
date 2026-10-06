from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.services.soil_service import (
    SoilServiceError,
)

from app.services.soilgrids_wcs import (
    get_soil_context_by_coordinates,
)

from app.services.soilgrids_rootzone import (
    get_root_zone_soil_context,
)


router = APIRouter(
    prefix="/api/soil",
    tags=["soil"],
)


# ============================================================
# SURFACE SOIL â€” 0-5 CM
# ============================================================

@router.get("/context")
def get_soil_context(
    latitude: float = Query(
        ...,
        ge=-90,
        le=90,
    ),

    longitude: float = Query(
        ...,
        ge=-180,
        le=180,
    ),
):

    try:

        return (
            get_soil_context_by_coordinates(
                latitude=latitude,
                longitude=longitude,
            )
        )

    except SoilServiceError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ============================================================
# ROOT-ZONE SOIL â€” 0-30 CM
# ============================================================

@router.get("/root-zone")
def get_root_zone_context(
    latitude: float = Query(
        ...,
        ge=-90,
        le=90,
    ),

    longitude: float = Query(
        ...,
        ge=-180,
        le=180,
    ),
):

    try:

        return (
            get_root_zone_soil_context(
                latitude=latitude,
                longitude=longitude,
            )
        )

    except SoilServiceError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
