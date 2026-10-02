import math

import pytest

import app.services.soilgrids_wcs as soilgrids_wcs

from app.services.soil_service import (
    SoilServiceError,
)


# ============================================================
# COORDINATE TRANSFORMATION
# ============================================================

def test_coordinate_transformation():

    x, y = (
        soilgrids_wcs
        .to_soilgrids_coordinates(
            latitude=13.0837,
            longitude=80.2702,
        )
    )

    assert math.isfinite(x)
    assert math.isfinite(y)


# ============================================================
# INVALID COORDINATES
# ============================================================

def test_invalid_latitude_rejected():

    with pytest.raises(
        SoilServiceError
    ):

        (
            soilgrids_wcs
            .to_soilgrids_coordinates(
                latitude=100.0,
                longitude=80.0,
            )
        )


# ============================================================
# COMPLETE PIPELINE WITHOUT INTERNET
# ============================================================

def test_soil_context_with_mock_values(
    monkeypatch,
):

    fake_values = {
        "phh2o": 65.0,
        "sand": 450.0,
        "silt": 300.0,
        "clay": 250.0,
    }


    def fake_fetch(
        property_name,
        x,
        y,
    ):

        return fake_values[
            property_name
        ]


    monkeypatch.setattr(
        soilgrids_wcs,
        "_fetch_raw_property",
        fake_fetch,
    )


    result = (
        soilgrids_wcs
        .get_soil_context_by_coordinates(
            latitude=13.0837,
            longitude=80.2702,
        )
    )


    assert (
        result["soil"]["soil_ph"]
        == 6.5
    )

    assert (
        result["soil"]["sand_percent"]
        == 45.0
    )

    assert (
        result["soil"]["silt_percent"]
        == 30.0
    )

    assert (
        result["soil"]["clay_percent"]
        == 25.0
    )

    assert (
        result["soil"][
            "dominant_texture_component"
        ]
        == "sand"
    )

    assert (
        result["source"]
        == "SoilGrids WCS"
    )