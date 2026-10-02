import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AdvisoryRun, RegistryEntry
from app.schemas import (
    AdvisoryRequest,
    AdvisoryResponse,
)
from app.services.constraint_engine import (
    evaluate_advisory,
)


router = APIRouter(
    prefix="/api/advisory",
    tags=["advisory"],
)


@router.post(
    "",
    response_model=AdvisoryResponse,
)
def get_advisory(
    payload: AdvisoryRequest,
    db: Session = Depends(get_db),
):

    # ========================================================
    # 1. FIND VERIFIED REAL REGISTRY CANDIDATES
    # ========================================================

    stmt = (
        select(RegistryEntry)
        .where(
            RegistryEntry.crop.ilike(
                payload.crop.strip()
            ),

            RegistryEntry.pest.ilike(
                payload.pest.strip()
            ),

            RegistryEntry.verified.is_(True),

            RegistryEntry.is_test_data.is_(False),
        )
    )

    candidates = (
        db.execute(stmt)
        .scalars()
        .all()
    )

    # ========================================================
    # 2. NO VERIFIED CROP-PEST MATCH
    # ========================================================

    if not candidates:

        result = AdvisoryResponse(
            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "No verified CIB&RC registry match "
                "was found for this crop-pest combination. "
                "The system will not guess."
            ),

            fired_rules=[
                "registration_missing"
            ],

            registry_verified=False,

            test_mode=False,
        )

    # ========================================================
    # 3. MULTIPLE VERIFIED CANDIDATES
    # ========================================================

    elif len(candidates) > 1:

        result = AdvisoryResponse(
            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                f"{len(candidates)} verified registry "
                "candidates were found. Additional farmer "
                "context is required before selecting a "
                "safe registered option."
            ),

            fired_rules=[
                "registration_exists",
                "multiple_candidates_require_context",
            ],

            registry_verified=True,

            test_mode=False,
        )

    # ========================================================
    # 4. EXACTLY ONE VERIFIED CANDIDATE
    # ========================================================

    else:

        registry_entry = candidates[0]

        evaluated = evaluate_advisory(
            registry_entry=registry_entry,

            field_area=payload.field_area,

            area_unit=payload.area_unit,

            expected_harvest_days=(
                payload.expected_harvest_days
            ),
        )

        result = AdvisoryResponse(
            status=evaluated.status,

            active_ingredient=(
                evaluated.active_ingredient
            ),

            scaled_dose_min=(
                evaluated.scaled_dose_min
            ),

            scaled_dose_max=(
                evaluated.scaled_dose_max
            ),

            dose_unit=(
                evaluated.dose_unit
            ),

            explanation=(
                evaluated.explanation
            ),

            fired_rules=(
                evaluated.fired_rules
            ),

            registry_verified=True,

            test_mode=False,
        )

    # ========================================================
    # 5. SAVE ADVISORY RUN
    # ========================================================

    advisory_log = AdvisoryRun(
        farmer_id=payload.farmer_id,

        crop=payload.crop,

        pest=payload.pest,

        decision=result.status,

        explanation=result.explanation,

        fired_rules=json.dumps(
            result.fired_rules
        ),
    )

    db.add(advisory_log)

    db.commit()

    return result