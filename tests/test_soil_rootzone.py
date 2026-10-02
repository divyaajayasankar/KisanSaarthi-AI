import pytest

from app.services.soil_rootzone import (
    RootZoneSoilError,
    SoilLayer,
    aggregate_root_zone,
)


# ============================================================
# NORMAL ROOT-ZONE AGGREGATION
# ============================================================

def test_root_zone_weighted_average():

    layers = [

        SoilLayer(
            depth_top_cm=0,
            depth_bottom_cm=5,
            soil_ph=6.0,
            sand_percent=50,
            silt_percent=20,
            clay_percent=30,
        ),

        SoilLayer(
            depth_top_cm=5,
            depth_bottom_cm=15,
            soil_ph=6.5,
            sand_percent=45,
            silt_percent=25,
            clay_percent=30,
        ),

        SoilLayer(
            depth_top_cm=15,
            depth_bottom_cm=30,
            soil_ph=7.0,
            sand_percent=40,
            silt_percent=30,
            clay_percent=30,
        ),
    ]


    result = aggregate_root_zone(
        layers
    )


    assert (
        result.depth_top_cm
        == 0
    )

    assert (
        result.depth_bottom_cm
        == 30
    )


    # Depth-weighted:
    #
    # (6.0*5 + 6.5*10 + 7.0*15) / 30
    # = 6.67

    assert (
        result.soil_ph
        == 6.67
    )


    assert (
        result.clay_percent
        == 30.0
    )


    assert (
        result.dominant_texture_component
        == "sand"
    )


# ============================================================
# INVALID PH
# ============================================================

def test_invalid_ph_rejected():

    layers = [

        SoilLayer(
            depth_top_cm=0,
            depth_bottom_cm=5,
            soil_ph=0,
            sand_percent=50,
            silt_percent=20,
            clay_percent=30,
        )
    ]


    with pytest.raises(
        RootZoneSoilError
    ):

        aggregate_root_zone(
            layers
        )


# ============================================================
# INVALID TEXTURE
# ============================================================

def test_invalid_texture_total_rejected():

    layers = [

        SoilLayer(
            depth_top_cm=0,
            depth_bottom_cm=5,
            soil_ph=6.5,
            sand_percent=20,
            silt_percent=20,
            clay_percent=20,
        )
    ]


    with pytest.raises(
        RootZoneSoilError
    ):

        aggregate_root_zone(
            layers
        )


# ============================================================
# EMPTY INPUT
# ============================================================

def test_empty_layers_rejected():

    with pytest.raises(
        RootZoneSoilError
    ):

        aggregate_root_zone(
            []
        )