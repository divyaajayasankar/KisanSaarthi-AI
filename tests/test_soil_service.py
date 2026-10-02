import pytest

from app.services.soil_service import (
    SoilServiceError,
    convert_soilgrids_ph,
    convert_texture_fraction,
    normalize_soilgrids_values,
)


# ============================================================
# PH CONVERSION
# ============================================================

def test_ph_conversion():

    result = convert_soilgrids_ph(
        67
    )

    assert result == 6.7


def test_invalid_ph_rejected():

    with pytest.raises(
        SoilServiceError
    ):

        convert_soilgrids_ph(
            200
        )


# ============================================================
# TEXTURE CONVERSION
# ============================================================

def test_texture_conversion():

    result = convert_texture_fraction(
        420,
        "sand",
    )

    assert result == 42.0


def test_invalid_texture_rejected():

    with pytest.raises(
        SoilServiceError
    ):

        convert_texture_fraction(
            1500,
            "clay",
        )


# ============================================================
# COMPLETE NORMALIZATION
# ============================================================

def test_normalize_soil_context():

    result = normalize_soilgrids_values(
        raw_phh2o=65,
        raw_sand=450,
        raw_silt=300,
        raw_clay=250,
    )


    assert result.soil_ph == 6.5

    assert result.sand_percent == 45.0

    assert result.silt_percent == 30.0

    assert result.clay_percent == 25.0

    assert (
        result.dominant_texture_component
        == "sand"
    )

    assert result.source == "SoilGrids"