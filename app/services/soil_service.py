from dataclasses import dataclass


# ============================================================
# SOIL SERVICE ERRORS
# ============================================================

class SoilServiceError(Exception):
    """
    Raised when soil information is missing or invalid.
    """

    pass


# ============================================================
# NORMALIZED SOIL CONTEXT
# ============================================================

@dataclass
class SoilContext:
    soil_ph: float

    sand_percent: float
    silt_percent: float
    clay_percent: float

    dominant_texture_component: str

    source: str = "SoilGrids"


# ============================================================
# SOILGRIDS VALUE CONVERSION
# ============================================================

def convert_soilgrids_ph(
    raw_phh2o: float,
) -> float:
    """
    SoilGrids stores pH in mapped units of pH x 10.

    Example:
        raw value 67
            ->
        pH 6.7
    """

    try:
        value = float(raw_phh2o)

    except (TypeError, ValueError) as exc:

        raise SoilServiceError(
            "Soil pH value is not numeric."
        ) from exc


    ph = value / 10.0


    if ph < 0 or ph > 14:

        raise SoilServiceError(
            "Converted soil pH is outside "
            "the valid 0-14 range."
        )


    return round(
        ph,
        2,
    )


# ============================================================
# TEXTURE FRACTION CONVERSION
# ============================================================

def convert_texture_fraction(
    raw_value: float,
    property_name: str,
) -> float:
    """
    SoilGrids sand, silt and clay values are stored
    in g/kg mapped units.

    Divide by 10 to obtain percentage.

    Example:
        420
            ->
        42%
    """

    try:
        value = float(raw_value)

    except (TypeError, ValueError) as exc:

        raise SoilServiceError(
            f"{property_name} value is not numeric."
        ) from exc


    percent = value / 10.0


    if percent < 0 or percent > 100:

        raise SoilServiceError(
            f"{property_name} percentage is outside "
            "the valid 0-100 range."
        )


    return round(
        percent,
        2,
    )


# ============================================================
# DOMINANT TEXTURE COMPONENT
# ============================================================

def get_dominant_texture_component(
    sand_percent: float,
    silt_percent: float,
    clay_percent: float,
) -> str:
    """
    Return only the dominant measured texture component.

    IMPORTANT:
    This is not yet a USDA soil texture class.

    We deliberately avoid inventing a soil classification
    until a verified classification rule is added.
    """

    values = {
        "sand": sand_percent,
        "silt": silt_percent,
        "clay": clay_percent,
    }


    return max(
        values,
        key=values.get,
    )


# ============================================================
# NORMALIZE SOILGRIDS DATA
# ============================================================

def normalize_soilgrids_values(
    raw_phh2o: float,
    raw_sand: float,
    raw_silt: float,
    raw_clay: float,
) -> SoilContext:
    """
    Convert raw SoilGrids mapped values into farmer-advisory
    soil context.

    No crop recommendation is made here.

    This layer only converts and validates evidence.
    """

    soil_ph = convert_soilgrids_ph(
        raw_phh2o
    )


    sand_percent = convert_texture_fraction(
        raw_sand,
        "sand",
    )


    silt_percent = convert_texture_fraction(
        raw_silt,
        "silt",
    )


    clay_percent = convert_texture_fraction(
        raw_clay,
        "clay",
    )


    dominant_component = (
        get_dominant_texture_component(
            sand_percent=sand_percent,
            silt_percent=silt_percent,
            clay_percent=clay_percent,
        )
    )


    return SoilContext(
        soil_ph=soil_ph,

        sand_percent=sand_percent,

        silt_percent=silt_percent,

        clay_percent=clay_percent,

        dominant_texture_component=(
            dominant_component
        ),

        source="SoilGrids",
    )