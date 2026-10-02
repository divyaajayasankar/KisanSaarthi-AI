import pytest

import app.services.soilgrids_rootzone as rootzone


# ============================================================
# MOCK SOILGRIDS VALUES
# ============================================================

MOCK_VALUES = {

    "0-5cm": {
        "phh2o": 60,
        "sand": 500,
        "silt": 200,
        "clay": 300,
    },

    "5-15cm": {
        "phh2o": 65,
        "sand": 450,
        "silt": 250,
        "clay": 300,
    },

    "15-30cm": {
        "phh2o": 70,
        "sand": 400,
        "silt": 300,
        "clay": 300,
    },
}


# ============================================================
# TEST COMPLETE ROOT-ZONE PIPELINE
# ============================================================

def test_live_root_zone_pipeline_mocked(
    monkeypatch,
):

    def fake_fetch(
        property_name,
        depth,
        x,
        y,
    ):

        return (
            MOCK_VALUES[
                depth
            ][
                property_name
            ]
        )


    monkeypatch.setattr(
        rootzone,
        "_fetch_property_for_depth",
        fake_fetch,
    )


    result = (
        rootzone
        .get_root_zone_soil_context(
            latitude=11.0,
            longitude=77.0,
        )
    )


    assert len(
        result["layers"]
    ) == 3


    assert (
        result["root_zone"][
            "depth_top_cm"
        ]
        == 0
    )


    assert (
        result["root_zone"][
            "depth_bottom_cm"
        ]
        == 30
    )


    assert (
        result["root_zone"][
            "soil_ph"
        ]
        == 6.67
    )


    assert (
        result["root_zone"][
            "sand_percent"
        ]
        == 43.33
    )


    assert (
        result["root_zone"][
            "silt_percent"
        ]
        == 26.67
    )


    assert (
        result["root_zone"][
            "clay_percent"
        ]
        == 30.0
    )


    assert (
        result["root_zone"][
            "dominant_texture_component"
        ]
        == "sand"
    )


    assert (
        result["root_zone_depth"]
        == "0-30cm"
    )


# ============================================================
# TEST ALL REQUIRED DEPTHS USED
# ============================================================

def test_three_standard_depths_requested(
    monkeypatch,
):

    requested_depths = []


    def fake_fetch(
        property_name,
        depth,
        x,
        y,
    ):

        requested_depths.append(
            depth
        )

        return (
            MOCK_VALUES[
                depth
            ][
                property_name
            ]
        )


    monkeypatch.setattr(
        rootzone,
        "_fetch_property_for_depth",
        fake_fetch,
    )


    rootzone.get_root_zone_soil_context(
        latitude=11.0,
        longitude=77.0,
    )


    assert "0-5cm" in requested_depths

    assert "5-15cm" in requested_depths

    assert "15-30cm" in requested_depths