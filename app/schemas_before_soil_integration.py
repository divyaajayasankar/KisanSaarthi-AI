from pydantic import BaseModel, Field


# ============================================================
# FARMER PROFILE SCHEMAS
# ============================================================

class FarmerCreate(BaseModel):
    farmer_name: str | None = None

    preferred_language: str = "English"

    state: str | None = None

    district: str | None = None

    crop: str | None = None

    pest: str | None = None

    field_area: float | None = Field(
        default=None,
        gt=0,
    )

    area_unit: str | None = None

    expected_harvest_days: int | None = Field(
        default=None,
        ge=0,
    )

    growth_stage: str | None = None


class FarmerOut(FarmerCreate):
    id: int

    model_config = {
        "from_attributes": True
    }


# ============================================================
# ADVISORY REQUEST
# ============================================================

class AdvisoryRequest(BaseModel):
    farmer_id: int | None = None

    crop: str

    pest: str

    field_area: float = Field(
        gt=0,
    )

    area_unit: str

    expected_harvest_days: int = Field(
        ge=0,
    )

    # --------------------------------------------------------
    # LOCATION CONTEXT FOR LIVE WEATHER
    # --------------------------------------------------------

    state: str | None = None

    district: str | None = None


# ============================================================
# ADVISORY RESPONSE
# ============================================================

class AdvisoryResponse(BaseModel):
    status: str

    active_ingredient: str | None = None

    scaled_dose_min: float | None = None

    scaled_dose_max: float | None = None

    dose_unit: str | None = None

    explanation: str

    fired_rules: list[str]

    registry_verified: bool = False

    test_mode: bool = False

    # --------------------------------------------------------
    # WEATHER RESULT
    # --------------------------------------------------------

    weather_status: str | None = None

    weather_summary: dict | None = None

    weather_source: str | None = None