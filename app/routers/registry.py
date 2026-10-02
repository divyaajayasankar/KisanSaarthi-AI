from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RegistryEntry


router = APIRouter(
    prefix="/api/registry",
    tags=["registry"],
)


@router.get("/search")
def search_registry(
    crop: str = Query(...),
    pest: str = Query(...),
    db: Session = Depends(get_db),
):

    stmt = (
        select(RegistryEntry)
        .where(
            RegistryEntry.crop.ilike(
                crop.strip()
            ),

            RegistryEntry.pest.ilike(
                pest.strip()
            ),

            RegistryEntry.verified.is_(True),

            RegistryEntry.is_test_data.is_(False),
        )
    )

    rows = (
        db.execute(stmt)
        .scalars()
        .all()
    )

    return {
        "crop": crop,
        "pest": pest,
        "count": len(rows),

        "results": [
            {
                "id": row.id,

                "crop": row.crop,

                "pest": row.pest,

                "active_ingredient":
                    row.active_ingredient,

                "formulation":
                    row.formulation,

                "dose_min_per_hectare":
                    row.dose_min_per_hectare,

                "dose_max_per_hectare":
                    row.dose_max_per_hectare,

                "dose_unit":
                    row.dose_unit,

                "water_volume_l_per_ha":
                    row.water_volume_l_per_ha,

                "phi_days":
                    row.phi_days,

                "source_document":
                    row.source_document,

                "source_page":
                    row.source_page,

                "source_url":
                    row.source_url,

                "source_date":
                    row.source_date,

                "verified":
                    row.verified,
            }

            for row in rows
        ],
    }