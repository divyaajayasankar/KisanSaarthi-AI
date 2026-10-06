from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from sqlalchemy.orm import Session

from app.db import get_db

from app.models_crop_soil import (
    CropSoilRule,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/crop-soil",
    tags=["crop-soil"],
)


# ============================================================
# SEARCH VERIFIED CROP-SOIL RULE
# ============================================================

@router.get("/search")
def search_crop_soil_rule(

    crop: str = Query(
        ...,
        min_length=1,
    ),

    db: Session = Depends(
        get_db
    ),
):

    crop_clean = crop.strip()


    rules = (
        db.query(
            CropSoilRule
        )
        .filter(
            CropSoilRule.crop.ilike(
                crop_clean
            ),

            CropSoilRule.verified.is_(
                True
            ),
        )
        .all()
    )


    return {

        "crop": crop_clean,

        "count": len(
            rules
        ),

        "rules": [

            {

                "id": rule.id,

                "crop": rule.crop,

                "min_ph": (
                    rule.min_ph
                ),

                "max_ph": (
                    rule.max_ph
                ),

                "preferred_texture": (
                    rule.preferred_texture
                ),

                "verified": (
                    rule.verified
                ),

                "source": {

                    "document": (
                        rule.source_document
                    ),

                    "page": (
                        rule.source_page
                    ),

                    "url": (
                        rule.source_url
                    ),

                    "date": (
                        rule.source_date
                    ),
                },
            }

            for rule in rules
        ],
    }
