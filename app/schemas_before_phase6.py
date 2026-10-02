from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


# ============================================================
# FARMER CREATE
# ============================================================

class FarmerCreate(BaseModel):

    farmer_name: str

    preferred_language: str

    state: str

    district: str

    crop: str

    pest: str

    field_area: float = Field(
        ...,
        gt=0,
    )

    area_unit: str

    expected_harvest_days: int = Field(
        ...,
        ge=0,
    )

    growth_stage: str | None = None


# ============================================================
# FARMER OUTPUT
# ============================================================

class FarmerOut(
    FarmerCreate
):

    id: int

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# ADVISORY REQUEST
# ============================================================

class AdvisoryRequest(BaseModel):

    farmer_id: int | None = None

    crop: str

    pest: str

    field_area: float = Field(
        ...,
        gt=0,
    )

    area_unit: str

    expected_harvest_days: int = Field(
        ...,
        ge=0,
    )

    # --------------------------------------------------------
    # WEATHER CONTEXT
    # --------------------------------------------------------

    state: str | None = None

    district: str | None = None


    # --------------------------------------------------------
    # FIELD COORDINATES FOR SOIL CONTEXT
    # --------------------------------------------------------
    #
    # Soil should use the farmer's real field coordinates,
    # not the district/city centre.
    # --------------------------------------------------------

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )


# ============================================================
# ADVISORY RESPONSE
# ============================================================

class AdvisoryResponse(BaseModel):

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    status: str


    # --------------------------------------------------------
    # VERIFIED REGISTRY / DOSE
    # --------------------------------------------------------

    active_ingredient: str | None = None

    scaled_dose_min: float | None = None

    scaled_dose_max: float | None = None

    dose_unit: str | None = None


    # --------------------------------------------------------
    # EXPLANATION + RULE TRACE
    # --------------------------------------------------------

    explanation: str

    fired_rules: list[str]


    # --------------------------------------------------------
    # REGISTRY PROVENANCE
    # --------------------------------------------------------

    registry_verified: bool = False

    test_mode: bool = False


    # --------------------------------------------------------
    # WEATHER EVIDENCE
    # --------------------------------------------------------

    weather_status: str | None = None

    weather_summary: dict[str, Any] | None = None

    weather_source: str | None = None


    # --------------------------------------------------------
    # SOIL EVIDENCE
    # --------------------------------------------------------

    soil_status: str | None = None

    soil_summary: dict[str, Any] | None = None

    soil_source: str | None = None
    # --------------------------------------------------------
# VERIFIED CROP-SOIL SUITABILITY
# --------------------------------------------------------

soil_suitability_status: str | None = None

soil_rule: dict[str, Any] | None = None