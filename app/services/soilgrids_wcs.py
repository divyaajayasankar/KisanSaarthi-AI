from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
import truststore

# Make Python HTTP libraries use the Windows/system
# certificate store before SoilGrids networking starts.
truststore.inject_into_ssl()

from pyproj import Transformer
from rasterio.io import DatasetReader
import rasterio

from soilgrids import SoilGrids

from app.services.soil_service import (
    SoilServiceError,
    normalize_soilgrids_values,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEPTH = "0-5cm"
PREDICTION = "mean"

SOILGRIDS_CRS = (
    "urn:ogc:def:crs:EPSG::152160"
)

SOILGRIDS_PROJ = (
    "+proj=igh "
    "+lat_0=0 "
    "+lon_0=0 "
    "+datum=WGS84 "
    "+units=m "
    "+no_defs"
)


# ============================================================
# COORDINATE TRANSFORMER
# ============================================================

TRANSFORMER = Transformer.from_crs(
    "EPSG:4326",
    SOILGRIDS_PROJ,
    always_xy=True,
)


# ============================================================
# VALIDATE COORDINATES
# ============================================================

def validate_coordinates(
    latitude: float,
    longitude: float,
) -> None:

    if not -90 <= latitude <= 90:

        raise SoilServiceError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:

        raise SoilServiceError(
            "Longitude must be between -180 and 180."
        )


# ============================================================
# CONVERT LAT/LON TO SOILGRIDS CRS
# ============================================================

def to_soilgrids_coordinates(
    latitude: float,
    longitude: float,
) -> tuple[float, float]:

    validate_coordinates(
        latitude,
        longitude,
    )

    x, y = TRANSFORMER.transform(
        longitude,
        latitude,
    )

    return (
        float(x),
        float(y),
    )


# ============================================================
# READ BEST RASTER VALUE
# ============================================================

def _read_raster_value(
    raster_path: Path,
    property_name: str,
) -> float:
    """
    Read the pixel nearest the requested location.

    If the exact centre pixel is nodata, search outward
    through valid pixels in the small downloaded window.
    """

    try:

        with rasterio.open(
            raster_path
        ) as dataset:

            data = dataset.read(
                1,
                masked=True,
            )

            if data.size == 0:

                raise SoilServiceError(
                    "Downloaded SoilGrids raster is empty."
                )


            # =================================================
            # CENTRE PIXEL
            # =================================================

            center_row = (
                data.shape[0] // 2
            )

            center_col = (
                data.shape[1] // 2
            )

            center_value = data[
                center_row,
                center_col,
            ]


            # =================================================
            # USE VALID CENTRE VALUE
            # =================================================

            if not np.ma.is_masked(
                center_value
            ):

                value = float(
                    center_value
                )

                if _is_plausible_raw_value(
                    property_name,
                    value,
                ):

                    return value


            # =================================================
            # SEARCH VALID NEARBY PIXELS
            # =================================================

            candidates = []

            for row in range(
                data.shape[0]
            ):

                for col in range(
                    data.shape[1]
                ):

                    value = data[
                        row,
                        col,
                    ]

                    if np.ma.is_masked(
                        value
                    ):

                        continue


                    numeric_value = float(
                        value
                    )


                    if not _is_plausible_raw_value(
                        property_name,
                        numeric_value,
                    ):

                        continue


                    distance = (
                        (row - center_row) ** 2
                        + (col - center_col) ** 2
                    )


                    candidates.append(
                        (
                            distance,
                            numeric_value,
                        )
                    )


            if not candidates:

                raise SoilServiceError(
                    f"SoilGrids returned no usable "
                    f"{property_name} prediction "
                    "for this location."
                )


            # Nearest valid pixel.
            candidates.sort(
                key=lambda item: item[0]
            )


            return candidates[0][1]


    except SoilServiceError:

        raise


    except Exception as exc:

        raise SoilServiceError(
            "Unable to read downloaded "
            "SoilGrids raster."
        ) from exc


# ============================================================
# RAW-VALUE VALIDATION
# ============================================================

def _is_plausible_raw_value(
    property_name: str,
    value: float,
) -> bool:

    if not np.isfinite(
        value
    ):

        return False


    # SoilGrids pH is stored as pH × 10.
    if property_name == "phh2o":

        return (
            value > 0
            and value <= 140
        )


    # Texture properties are stored as g/kg.
    if property_name in {
        "sand",
        "silt",
        "clay",
    }:

        return (
            value >= 0
            and value <= 1000
        )


    return False


# ============================================================
# DOWNLOAD ONE SOIL PROPERTY
# ============================================================

def _fetch_raw_property(
    property_name: str,
    x: float,
    y: float,
) -> float:
    """
    Retrieve one SoilGrids coverage using the dedicated
    SoilGrids Python client.

    A 1.5 km x 1.5 km window is downloaded around the
    supplied farm coordinate.
    """

    coverage_id = (
        f"{property_name}_"
        f"{DEPTH}_"
        f"{PREDICTION}"
    )


    # 750 m on each side.
    half_window_m = 750.0


    west = x - half_window_m
    east = x + half_window_m

    south = y - half_window_m
    north = y + half_window_m


    try:

        with TemporaryDirectory() as temp_dir:

            output_path = (
                Path(temp_dir)
                / f"{property_name}.tif"
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
                    f"the {property_name} raster."
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
            f"{property_name} from SoilGrids. "
            f"Reason: {type(exc).__name__}: {exc}"
        ) from exc


# ============================================================
# TEXTURE VALIDATION
# ============================================================

def _validate_texture(
    raw_sand: float,
    raw_silt: float,
    raw_clay: float,
) -> None:

    total = (
        raw_sand
        + raw_silt
        + raw_clay
    )


    if total <= 0:

        raise SoilServiceError(
            "SoilGrids returned no usable "
            "soil-texture evidence."
        )


    # SoilGrids texture values are g/kg and should
    # approximately sum to 1000.
    #
    # Keep tolerance broad because these are model
    # predictions and may include rounding differences.

    if total < 700 or total > 1300:

        raise SoilServiceError(
            "SoilGrids returned inconsistent "
            "sand, silt and clay values."
        )


# ============================================================
# COMPLETE SOIL CONTEXT
# ============================================================

def get_soil_context_by_coordinates(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:

    validate_coordinates(
        latitude,
        longitude,
    )


    # ========================================================
    # PROJECT FARM COORDINATE
    # ========================================================

    x, y = to_soilgrids_coordinates(
        latitude=latitude,
        longitude=longitude,
    )


    # ========================================================
    # FETCH SOILGRIDS PROPERTIES
    # ========================================================

    raw_phh2o = _fetch_raw_property(
        "phh2o",
        x,
        y,
    )


    raw_sand = _fetch_raw_property(
        "sand",
        x,
        y,
    )


    raw_silt = _fetch_raw_property(
        "silt",
        x,
        y,
    )


    raw_clay = _fetch_raw_property(
        "clay",
        x,
        y,
    )


    # ========================================================
    # VALIDATE TEXTURE
    # ========================================================

    _validate_texture(
        raw_sand=raw_sand,
        raw_silt=raw_silt,
        raw_clay=raw_clay,
    )


    # ========================================================
    # NORMALIZE
    # ========================================================

    soil_context = (
        normalize_soilgrids_values(

            raw_phh2o=raw_phh2o,

            raw_sand=raw_sand,

            raw_silt=raw_silt,

            raw_clay=raw_clay,
        )
    )


    # ========================================================
    # RESPONSE
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


        "depth": DEPTH,


        "prediction": PREDICTION,


        "soil": asdict(
            soil_context
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