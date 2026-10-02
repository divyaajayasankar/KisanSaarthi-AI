from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

from app.models import (
    FarmerProfile,
    RegistryEntry,
)

from app.schemas import (
    AdvisoryRequest,
    AdvisoryResponse,
)

from app.services.constraint_engine import (
    evaluate_advisory,
)

from app.services.weather_service import (
    WeatherServiceError,
    get_location_weather,
)

from app.services.weather_rules import (
    evaluate_weather_safety,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api",
    tags=["advisory"],
)


# ============================================================
# LOCATION RESOLUTION
# ============================================================

def resolve_location(
    request: AdvisoryRequest,
    db: Session,
) -> tuple[str | None, str | None]:
    """
    Resolve state and district.

    Priority:
        1. Values supplied in current advisory request
        2. Saved farmer profile using farmer_id
    """

    state = None
    district = None

    if request.state:
        state = request.state.strip()

    if request.district:
        district = request.district.strip()


    # --------------------------------------------------------
    # REQUEST ALREADY HAS COMPLETE LOCATION
    # --------------------------------------------------------

    if state and district:
        return state, district


    # --------------------------------------------------------
    # TRY SAVED FARMER PROFILE
    # --------------------------------------------------------

    if request.farmer_id is not None:

        farmer = (
            db.query(FarmerProfile)
            .filter(
                FarmerProfile.id
                == request.farmer_id
            )
            .first()
        )

        if farmer is not None:

            if not state and farmer.state:
                state = farmer.state.strip()

            if not district and farmer.district:
                district = farmer.district.strip()


    return state, district


# ============================================================
# ADVISORY ENDPOINT
# ============================================================

@router.post(
    "/advisory",
    response_model=AdvisoryResponse,
)
def get_advisory(
    request: AdvisoryRequest,
    db: Session = Depends(get_db),
):

    # ========================================================
    # CLEAN INPUT
    # ========================================================

    crop = request.crop.strip()

    pest = request.pest.strip()


    # ========================================================
    # STEP 1 — SEARCH VERIFIED REAL REGISTRY
    # ========================================================

    candidates = (
        db.query(RegistryEntry)
        .filter(
            RegistryEntry.crop.ilike(crop),
            RegistryEntry.pest.ilike(pest),
            RegistryEntry.verified.is_(True),
            RegistryEntry.is_test_data.is_(False),
        )
        .all()
    )


    # ========================================================
    # STEP 2 — REGISTRATION MISSING
    # ========================================================

    if len(candidates) == 0:

        return AdvisoryResponse(

            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "No verified CIB&RC registry match was found "
                "for this crop-pest combination. "
                "The system will not guess."
            ),

            fired_rules=[
                "registration_missing"
            ],

            registry_verified=False,

            test_mode=False,

            weather_status=None,

            weather_summary=None,

            weather_source=None,
        )


    # ========================================================
    # STEP 3 — MULTIPLE CANDIDATES
    # ========================================================

    if len(candidates) > 1:

        return AdvisoryResponse(

            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "Multiple verified registry options were found "
                "for this crop-pest combination. Additional "
                "context is required before selecting an option."
            ),

            fired_rules=[
                "registration_exists",
                "multiple_candidates_require_context",
            ],

            registry_verified=True,

            test_mode=False,

            weather_status=None,

            weather_summary=None,

            weather_source=None,
        )


    # ========================================================
    # EXACTLY ONE VERIFIED REGISTRY ENTRY
    # ========================================================

    registry_entry = candidates[0]


    # ========================================================
    # STEP 4 — REGISTRY / DOSE / AREA / PHI RULES
    # ========================================================

    result = evaluate_advisory(

        registry_entry=registry_entry,

        field_area=request.field_area,

        area_unit=request.area_unit,

        expected_harvest_days=(
            request.expected_harvest_days
        ),
    )


    # ========================================================
    # STEP 5 — STOP IF PHI / DOSE / REGISTRY RULE FAILED
    # ========================================================

    if result.status != "recommend":

        return AdvisoryResponse(

            status=result.status,

            active_ingredient=result.active_ingredient,

            scaled_dose_min=result.scaled_dose_min,

            scaled_dose_max=result.scaled_dose_max,

            dose_unit=result.dose_unit,

            explanation=result.explanation,

            fired_rules=result.fired_rules,

            registry_verified=True,

            test_mode=False,

            weather_status=None,

            weather_summary=None,

            weather_source=None,
        )


    # ========================================================
    # STEP 6 — RESOLVE FARMER LOCATION
    # ========================================================

    state, district = resolve_location(
        request=request,
        db=db,
    )


    # ========================================================
    # STEP 7 — WEATHER CONTEXT REQUIRED
    # ========================================================

    if not state or not district:

        return AdvisoryResponse(

            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "A verified registry option was found and the "
                "PHI check passed, but state and district are "
                "required to verify weather conditions before "
                "issuing a spray recommendation."
            ),

            fired_rules=(
                result.fired_rules
                + [
                    "weather_context_missing"
                ]
            ),

            registry_verified=True,

            test_mode=False,

            weather_status="unavailable",

            weather_summary=None,

            weather_source=None,
        )


    # ========================================================
    # STEP 8 — FETCH LIVE WEATHER
    # ========================================================

    try:

        weather_data = get_location_weather(
            district=district,
            state=state,
        )

    except WeatherServiceError as exc:

        return AdvisoryResponse(

            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "The registry, dose and PHI checks passed, "
                "but current weather evidence could not be "
                "verified. The system will not issue a spray "
                "recommendation without verified weather data."
            ),

            fired_rules=(
                result.fired_rules
                + [
                    "weather_unavailable"
                ]
            ),

            registry_verified=True,

            test_mode=False,

            weather_status="unavailable",

            weather_summary=None,

            weather_source=None,
        )

    except Exception:

        # ----------------------------------------------------
        # FAIL SAFELY ON UNEXPECTED WEATHER ERROR
        # ----------------------------------------------------

        return AdvisoryResponse(

            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "Weather verification is temporarily "
                "unavailable. The system will not guess "
                "application conditions."
            ),

            fired_rules=(
                result.fired_rules
                + [
                    "weather_unavailable"
                ]
            ),

            registry_verified=True,

            test_mode=False,

            weather_status="unavailable",

            weather_summary=None,

            weather_source=None,
        )


    # ========================================================
    # STEP 9 — APPLY DETERMINISTIC WEATHER RULES
    # ========================================================

    weather_result = evaluate_weather_safety(
        weather_data["weather"]
    )


    # ========================================================
    # STEP 10 — UNSAFE WEATHER
    # ========================================================

    if weather_result.status == "delay":

        return AdvisoryResponse(

            status="delay",

            # ------------------------------------------------
            # IMPORTANT:
            # Do not return actionable dose while weather
            # conditions are unsuitable.
            # ------------------------------------------------

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                weather_result.explanation
            ),

            fired_rules=(
                result.fired_rules
                + weather_result.fired_rules
            ),

            registry_verified=True,

            test_mode=False,

            weather_status="delay",

            weather_summary=(
                weather_data["weather"]
            ),

            weather_source=(
                weather_data.get("source")
            ),
        )


    # ========================================================
    # STEP 11 — EVERYTHING PASSED
    # ========================================================

    return AdvisoryResponse(

        status="recommend",

        active_ingredient=(
            result.active_ingredient
        ),

        scaled_dose_min=(
            result.scaled_dose_min
        ),

        scaled_dose_max=(
            result.scaled_dose_max
        ),

        dose_unit=result.dose_unit,

        explanation=(
            result.explanation
            + " Weather safety checks also passed for "
            + f"{district}, {state}."
        ),

        fired_rules=(
            result.fired_rules
            + weather_result.fired_rules
        ),

        registry_verified=True,

        test_mode=False,

        weather_status="proceed",

        weather_summary=(
            weather_data["weather"]
        ),

        weather_source=(
            weather_data.get("source")
        ),
    )