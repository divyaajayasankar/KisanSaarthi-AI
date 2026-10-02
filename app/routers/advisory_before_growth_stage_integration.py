from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

from app.models import (
    FarmerProfile,
    RegistryEntry,
)

from app.models_crop_soil import (
    CropSoilRule,
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

from app.services.soil_service import (
    SoilServiceError,
)

from app.services.soilgrids_rootzone import (
    get_root_zone_soil_context,
)

from app.services.crop_soil_rules import (
    evaluate_crop_soil_rule,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api",
    tags=["advisory"],
)


# ============================================================
# RESOLVE WEATHER LOCATION
# ============================================================

def resolve_location(
    request: AdvisoryRequest,
    db: Session,
) -> tuple[str | None, str | None]:
    """
    Resolve state and district.

    Priority:
        1. Current advisory request
        2. Saved farmer profile
    """

    state = None
    district = None


    if request.state:

        state = request.state.strip()


    if request.district:

        district = request.district.strip()


    # --------------------------------------------------------
    # COMPLETE LOCATION ALREADY PROVIDED
    # --------------------------------------------------------

    if state and district:

        return (
            state,
            district,
        )


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

            if (
                not state
                and farmer.state
            ):

                state = (
                    farmer.state.strip()
                )


            if (
                not district
                and farmer.district
            ):

                district = (
                    farmer.district.strip()
                )


    return (
        state,
        district,
    )


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
    # STEP 1 — CLEAN INPUT
    # ========================================================

    crop = request.crop.strip()

    pest = request.pest.strip()


    # ========================================================
    # STEP 2 — FIND VERIFIED CIB&RC REGISTRY MATCH
    # ========================================================

    candidates = (
        db.query(RegistryEntry)
        .filter(
            RegistryEntry.crop.ilike(
                crop
            ),

            RegistryEntry.pest.ilike(
                pest
            ),

            RegistryEntry.verified.is_(
                True
            ),

            RegistryEntry.is_test_data.is_(
                False
            ),
        )
        .all()
    )


    # ========================================================
    # STEP 3 — REGISTRATION MISSING
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

            soil_status=None,

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=None,

            soil_rule=None,
        )


    # ========================================================
    # STEP 4 — MULTIPLE REGISTRY CANDIDATES
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

            soil_status=None,

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=None,

            soil_rule=None,
        )


    # ========================================================
    # EXACTLY ONE VERIFIED REGISTRY ENTRY
    # ========================================================

    registry_entry = candidates[0]


    # ========================================================
    # STEP 5 — REGISTRY + DOSE + AREA + PHI
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
    # STEP 6 — STOP IF BASIC CONSTRAINT FAILS
    # ========================================================

    if result.status != "recommend":

        return AdvisoryResponse(

            status=result.status,

            active_ingredient=(
                result.active_ingredient
            ),

            scaled_dose_min=(
                result.scaled_dose_min
            ),

            scaled_dose_max=(
                result.scaled_dose_max
            ),

            dose_unit=(
                result.dose_unit
            ),

            explanation=(
                result.explanation
            ),

            fired_rules=(
                result.fired_rules
            ),

            registry_verified=True,

            test_mode=False,

            weather_status=None,

            weather_summary=None,

            weather_source=None,

            soil_status=None,

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=None,

            soil_rule=None,
        )


    # ========================================================
    # STEP 7 — RESOLVE WEATHER LOCATION
    # ========================================================

    state, district = (
        resolve_location(
            request=request,
            db=db,
        )
    )


    # ========================================================
    # STEP 8 — WEATHER CONTEXT REQUIRED
    # ========================================================

    if not state or not district:

        return AdvisoryResponse(

            status="abstain",

            active_ingredient=None,

            scaled_dose_min=None,

            scaled_dose_max=None,

            dose_unit=None,

            explanation=(
                "The registry, dose and PHI checks passed, "
                "but state and district are required to verify "
                "weather conditions before issuing a spray "
                "recommendation."
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

            soil_status=None,

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=None,

            soil_rule=None,
        )


    # ========================================================
    # STEP 9 — FETCH LIVE WEATHER
    # ========================================================

    try:

        weather_data = (
            get_location_weather(
                district=district,
                state=state,
            )
        )


    except WeatherServiceError:

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

            soil_status=None,

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=None,

            soil_rule=None,
        )


    except Exception:

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

            soil_status=None,

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=None,

            soil_rule=None,
        )


    # ========================================================
    # STEP 10 — APPLY WEATHER SAFETY RULES
    # ========================================================

    weather_result = (
        evaluate_weather_safety(
            weather_data[
                "weather"
            ]
        )
    )


    # ========================================================
    # STEP 11 — UNSAFE WEATHER -> DELAY
    # ========================================================

    if weather_result.status == "delay":

        return AdvisoryResponse(

            status="delay",

            # ------------------------------------------------
            # Do not expose actionable pesticide information
            # when spray conditions are unsuitable.
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
                weather_data[
                    "weather"
                ]
            ),

            weather_source=(
                weather_data.get(
                    "source"
                )
            ),

            # ------------------------------------------------
            # Soil does not need evaluation once weather
            # already blocks the application.
            # ------------------------------------------------

            soil_status="not_evaluated",

            soil_summary=None,

            soil_source=None,

            soil_suitability_status=(
                "not_evaluated"
            ),

            soil_rule=None,
        )


    # ========================================================
    # STEP 12 — WEATHER PASSED
    # ========================================================

    fired_rules = (
        result.fired_rules
        + weather_result.fired_rules
    )


    # ========================================================
    # STEP 13 — INITIALIZE SOIL VARIABLES
    # ========================================================

    soil_status = None

    soil_summary = None

    soil_source = None

    soil_explanation = ""


    soil_suitability_status = None

    soil_rule_summary = None


    # ========================================================
    # STEP 14 — FIELD COORDINATES
    # ========================================================

    latitude = request.latitude

    longitude = request.longitude


    # ========================================================
    # STEP 15 — BOTH COORDINATES PROVIDED
    # ========================================================

    if (
        latitude is not None
        and longitude is not None
    ):

        try:

            # =================================================
            # FETCH 0-30 CM ROOT-ZONE SOIL
            # =================================================

            soil_data = (
                get_root_zone_soil_context(

                    latitude=latitude,

                    longitude=longitude,
                )
            )


            soil_status = "available"


            soil_summary = {

                "coordinates": (
                    soil_data.get(
                        "coordinates"
                    )
                ),

                "root_zone_depth": (
                    soil_data.get(
                        "root_zone_depth"
                    )
                ),

                "root_zone": (
                    soil_data.get(
                        "root_zone"
                    )
                ),

                "aggregation": (
                    soil_data.get(
                        "aggregation"
                    )
                ),
            }


            soil_source = (
                soil_data.get(
                    "source"
                )
            )


            fired_rules.append(
                "soil_context_available"
            )


            soil_explanation = (
                " A 0-30 cm SoilGrids root-zone soil "
                "profile was successfully retrieved for "
                "the supplied field coordinates."
            )


            # =================================================
            # STEP 16 — FIND VERIFIED CROP-SOIL RULE
            # =================================================

            verified_soil_rules = (
                db.query(
                    CropSoilRule
                )
                .filter(

                    CropSoilRule.crop.ilike(
                        crop
                    ),

                    CropSoilRule.verified.is_(
                        True
                    ),
                )
                .all()
            )


            # =================================================
            # NO VERIFIED CROP-SOIL RULE
            # =================================================

            if len(
                verified_soil_rules
            ) == 0:

                soil_suitability_status = (
                    "not_evaluated"
                )


                fired_rules.append(
                    "soil_rule_missing"
                )


                soil_explanation += (
                    " No verified crop-specific soil pH "
                    f"rule is available for {crop}, so "
                    "soil suitability was not inferred."
                )


            # =================================================
            # MULTIPLE VERIFIED RULES
            # =================================================

            elif len(
                verified_soil_rules
            ) > 1:

                soil_suitability_status = (
                    "not_evaluated"
                )


                fired_rules.append(
                    "multiple_soil_rules_require_resolution"
                )


                soil_explanation += (
                    " Multiple verified crop-soil rules "
                    f"were found for {crop}; therefore "
                    "the system did not automatically "
                    "select one."
                )


            # =================================================
            # EXACTLY ONE VERIFIED RULE
            # =================================================

            else:

                crop_soil_rule = (
                    verified_soil_rules[0]
                )


                # =============================================
                # OBSERVED ROOT-ZONE PH
                # =============================================

                observed_ph = float(

                    soil_data[
                        "root_zone"
                    ][
                        "soil_ph"
                    ]
                )


                # =============================================
                # EVALUATE PH AGAINST VERIFIED RANGE
                # =============================================

                soil_rule_result = (
                    evaluate_crop_soil_rule(

                        crop=crop,

                        observed_ph=(
                            observed_ph
                        ),

                        min_ph=(
                            crop_soil_rule.min_ph
                        ),

                        max_ph=(
                            crop_soil_rule.max_ph
                        ),

                        verified=(
                            crop_soil_rule.verified
                        ),
                    )
                )


                soil_suitability_status = (
                    soil_rule_result.status
                )


                fired_rules.extend(
                    soil_rule_result.fired_rules
                )


                # =============================================
                # VERIFIED RULE EVIDENCE
                # =============================================

                soil_rule_summary = {

                    "crop": (
                        crop_soil_rule.crop
                    ),

                    "observed_root_zone_ph": (
                        observed_ph
                    ),

                    "verified_min_ph": (
                        crop_soil_rule.min_ph
                    ),

                    "verified_max_ph": (
                        crop_soil_rule.max_ph
                    ),

                    "preferred_texture": (
                        crop_soil_rule
                        .preferred_texture
                    ),

                    "evaluation": (
                        soil_rule_result.status
                    ),

                    "source_document": (
                        crop_soil_rule
                        .source_document
                    ),

                    "source_page": (
                        crop_soil_rule
                        .source_page
                    ),

                    "source_url": (
                        crop_soil_rule
                        .source_url
                    ),
                }


                soil_explanation += (
                    " "
                    + soil_rule_result.explanation
                )


        # ====================================================
        # SOILGRIDS / SOIL SERVICE FAILURE
        # ====================================================

        except SoilServiceError:

            soil_status = "unavailable"

            soil_summary = None

            soil_source = None

            soil_suitability_status = (
                "not_evaluated"
            )

            soil_rule_summary = None


            fired_rules.append(
                "soil_context_unavailable"
            )


            soil_explanation = (
                " Soil evidence could not be retrieved, "
                "so no soil-based rule was applied."
            )


        # ====================================================
        # UNEXPECTED SOIL FAILURE
        # ====================================================

        except Exception:

            soil_status = "unavailable"

            soil_summary = None

            soil_source = None

            soil_suitability_status = (
                "not_evaluated"
            )

            soil_rule_summary = None


            fired_rules.append(
                "soil_context_unavailable"
            )


            soil_explanation = (
                " Soil evidence could not be retrieved, "
                "so no soil-based rule was applied."
            )


    # ========================================================
    # STEP 17 — ONLY ONE COORDINATE PROVIDED
    # ========================================================

    elif (
        latitude is not None
        or longitude is not None
    ):

        soil_status = "incomplete"

        soil_summary = None

        soil_source = None

        soil_suitability_status = (
            "not_evaluated"
        )

        soil_rule_summary = None


        fired_rules.append(
            "soil_coordinates_incomplete"
        )


        soil_explanation = (
            " Soil context was not evaluated because "
            "both field latitude and longitude are required."
        )


    # ========================================================
    # STEP 18 — NO FIELD COORDINATES
    # ========================================================

    else:

        soil_status = "not_provided"

        soil_summary = None

        soil_source = None

        soil_suitability_status = (
            "not_evaluated"
        )

        soil_rule_summary = None


        fired_rules.append(
            "soil_context_not_provided"
        )


        soil_explanation = (
            " Field coordinates were not provided, "
            "so no soil-based rule was applied."
        )


    # ========================================================
    # STEP 19 — FINAL PERSONALIZED ADVISORY
    # ========================================================
    #
    # IMPORTANT:
    #
    # Soil suitability currently adds a contextual warning
    # or suitability result.
    #
    # An unsuitable crop-soil pH does NOT automatically change
    # the pesticide decision to ABSTAIN because crop-soil
    # suitability and pesticide application safety are
    # separate decisions.
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

        dose_unit=(
            result.dose_unit
        ),

        explanation=(
            result.explanation
            + " Weather safety checks also passed for "
            + f"{district}, {state}."
            + soil_explanation
        ),

        fired_rules=(
            fired_rules
        ),

        registry_verified=True,

        test_mode=False,

        weather_status="proceed",

        weather_summary=(
            weather_data[
                "weather"
            ]
        ),

        weather_source=(
            weather_data.get(
                "source"
            )
        ),

        soil_status=(
            soil_status
        ),

        soil_summary=(
            soil_summary
        ),

        soil_source=(
            soil_source
        ),

        soil_suitability_status=(
            soil_suitability_status
        ),

        soil_rule=(
            soil_rule_summary
        ),
    )