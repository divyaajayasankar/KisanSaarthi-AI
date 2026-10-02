from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import truststore

# Use Windows/system certificates.
truststore.inject_into_ssl()

from soilgrids import SoilGrids

from app.services.soil_service import (
    SoilServiceError,
    normalize_soilgrids_values,
)

from app.services.soil_rootzone import (
    SoilLayer,
    RootZoneSoilError,
    aggregate_root_zone,
)

from app.services.soilgrids_wcs import (
    to_soilgrids_coordinates,
    _read_raster_value,
)


# ============================================================
# ROOT-ZONE DEPTH INTERVALS
# ============================================================

ROOT_ZONE_DEPTHS = [

    {
        "name": "0-5cm",
        "top_cm": 0,
        "bottom_cm": 5,
    },

    {
        "name": "5-15cm",
        "top_cm": 5,
        "bottom_cm": 15,
    },

    {
        "name": "15-30cm",
        "top_cm": 15,
        "bottom_cm": 30,
    },
]


SOILGRIDS_CRS = (
    "urn:ogc:def:crs:EPSG::152160"
)


# ============================================================
# FETCH PROPERTY FOR ONE DEPTH
# ============================================================

def _fetch_property_for_depth(
    property_name: str,
    depth: str,
    x: float,
    y: float,
) -> float:
    """
    Download one SoilGrids property for one depth.

    Example coverage:
        phh2o_5-15cm_mean
    """

    coverage_id = (
        f"{property_name}_"
        f"{depth}_"
        f"mean"
    )


    # ========================================================
    # SMALL WINDOW AROUND FIELD
    # ========================================================

    half_window_m = 750.0

    west = x - half_window_m
    east = x + half_window_m

    south = y - half_window_m
    north = y + half_window_m


    try:

        with TemporaryDirectory() as temp_dir:

            output_path = (
                Path(temp_dir)
                / f"{property_name}_{depth}.tif"
            )


            client = SoilGrids()


            client.get_coverage_data(

                service_id=property_name,

                coverage_id=coverage_id,

                west=west,

                south=south,

                east=east,

                north=north,

                crs=SOILGRIDS_CRS,

                output=str(
                    output_path
                ),

                resx=250,

                resy=250,
            )


            if not output_path.exists():

                raise SoilServiceError(
                    "SoilGrids did not create "
                    f"{property_name} raster "
                    f"for depth {depth}."
                )


            return _read_raster_value(

                raster_path=output_path,

                property_name=property_name,
            )


    except SoilServiceError:

        raise


    except Exception as exc:

        raise SoilServiceError(
            "Unable to retrieve "
            f"{property_name} for depth "
            f"{depth} from SoilGrids. "
            f"Reason: {type(exc).__name__}: {exc}"
        ) from exc


# ============================================================
# BUILD ONE SOIL LAYER
# ============================================================

def _get_soil_layer(
    depth_name: str,
    top_cm: int,
    bottom_cm: int,
    x: float,
    y: float,
) -> tuple[SoilLayer, dict[str, Any]]:
    """
    Retrieve and normalize one complete SoilGrids layer.
    """

    # ========================================================
    # FETCH RAW VALUES
    # ========================================================

    raw_ph = _fetch_property_for_depth(
        property_name="phh2o",
        depth=depth_name,
        x=x,
        y=y,
    )


    raw_sand = _fetch_property_for_depth(
        property_name="sand",
        depth=depth_name,
        x=x,
        y=y,
    )


    raw_silt = _fetch_property_for_depth(
        property_name="silt",
        depth=depth_name,
        x=x,
        y=y,
    )


    raw_clay = _fetch_property_for_depth(
        property_name="clay",
        depth=depth_name,
        x=x,
        y=y,
    )


    # ========================================================
    # NORMALIZE
    # ========================================================

    normalized = normalize_soilgrids_values(

        raw_phh2o=raw_ph,

        raw_sand=raw_sand,

        raw_silt=raw_silt,

        raw_clay=raw_clay,
    )


    # ========================================================
    # CREATE ROOT-ZONE LAYER
    # ========================================================

    layer = SoilLayer(

        depth_top_cm=top_cm,

        depth_bottom_cm=bottom_cm,

        soil_ph=normalized.soil_ph,

        sand_percent=normalized.sand_percent,

        silt_percent=normalized.silt_percent,

        clay_percent=normalized.clay_percent,
    )


    # ========================================================
    # RESPONSE VERSION
    # ========================================================

    layer_response = {

        "depth": depth_name,

        "depth_top_cm": top_cm,

        "depth_bottom_cm": bottom_cm,

        "soil_ph": normalized.soil_ph,

        "sand_percent": (
            normalized.sand_percent
        ),

        "silt_percent": (
            normalized.silt_percent
        ),

        "clay_percent": (
            normalized.clay_percent
        ),

        "dominant_texture_component": (
            normalized
            .dominant_texture_component
        ),
    }


    return (
        layer,
        layer_response,
    )


# ============================================================
# GET LIVE ROOT-ZONE SOIL CONTEXT
# ============================================================

def get_root_zone_soil_context(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    """
    Retrieve SoilGrids data for:

        0-5 cm
        5-15 cm
        15-30 cm

    and aggregate them into a 0-30 cm
    depth-weighted root-zone profile.
    """

    # ========================================================
    # TRANSFORM FIELD LOCATION
    # ========================================================

    x, y = to_soilgrids_coordinates(

        latitude=latitude,

        longitude=longitude,
    )


    soil_layers = []

    layer_responses = []


    # ========================================================
    # RETRIEVE THREE STANDARD DEPTHS
    # ========================================================

    for depth_info in ROOT_ZONE_DEPTHS:

        layer, response = (
            _get_soil_layer(

                depth_name=(
                    depth_info["name"]
                ),

                top_cm=(
                    depth_info["top_cm"]
                ),

                bottom_cm=(
                    depth_info["bottom_cm"]
                ),

                x=x,

                y=y,
            )
        )


        soil_layers.append(
            layer
        )


        layer_responses.append(
            response
        )


    # ========================================================
    # DEPTH-WEIGHTED 0-30 CM AGGREGATION
    # ========================================================

    try:

        root_zone = aggregate_root_zone(
            soil_layers
        )


    except RootZoneSoilError as exc:

        raise SoilServiceError(
            "Unable to construct a valid "
            "0-30 cm root-zone soil profile. "
            f"Reason: {exc}"
        ) from exc


    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {

        "coordinates": {

            "latitude": latitude,

            "longitude": longitude,
        },


        "soilgrids_coordinates": {

            "x": round(
                x,
                2,
            ),

            "y": round(
                y,
                2,
            ),
        },


        "layers": (
            layer_responses
        ),


        "root_zone": (
            asdict(
                root_zone
            )
        ),


        "aggregation": (
            "depth-weighted mean"
        ),


        "root_zone_depth": (
            "0-30cm"
        ),


        "source": (
            "SoilGrids WCS"
        ),


        "access_method": (
            "soilgrids-python-client"
        ),


        "source_url": (
            "https://maps.isric.org"
        ),
    }