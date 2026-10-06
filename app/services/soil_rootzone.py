from dataclasses import dataclass


# ============================================================
# ROOT-ZONE ERROR
# ============================================================

class RootZoneSoilError(Exception):
    """
    Raised when soil layers cannot be combined safely.
    """

    pass


# ============================================================
# SOIL LAYER
# ============================================================

@dataclass
class SoilLayer:
    depth_top_cm: float
    depth_bottom_cm: float

    soil_ph: float

    sand_percent: float
    silt_percent: float
    clay_percent: float


# ============================================================
# ROOT-ZONE RESULT
# ============================================================

@dataclass
class RootZoneSoilContext:
    depth_top_cm: float
    depth_bottom_cm: float

    soil_ph: float

    sand_percent: float
    silt_percent: float
    clay_percent: float

    dominant_texture_component: str

    source: str


# ============================================================
# VALIDATE LAYER
# ============================================================

def _validate_layer(
    layer: SoilLayer,
) -> None:

    if (
        layer.depth_bottom_cm
        <= layer.depth_top_cm
    ):

        raise RootZoneSoilError(
            "Soil layer depth is invalid."
        )


    if not 0 < layer.soil_ph <= 14:

        raise RootZoneSoilError(
            "Soil layer pH is invalid."
        )


    for name, value in {
        "sand": layer.sand_percent,
        "silt": layer.silt_percent,
        "clay": layer.clay_percent,
    }.items():

        if value < 0 or value > 100:

            raise RootZoneSoilError(
                f"{name} percentage is invalid."
            )


    texture_total = (
        layer.sand_percent
        + layer.silt_percent
        + layer.clay_percent
    )


    # Allow small prediction / rounding differences.
    if texture_total < 95 or texture_total > 105:

        raise RootZoneSoilError(
            "Sand, silt and clay percentages "
            "must approximately sum to 100."
        )


# ============================================================
# AGGREGATE ROOT ZONE
# ============================================================

def aggregate_root_zone(
    layers: list[SoilLayer],
) -> RootZoneSoilContext:
    """
    Combine SoilGrids layers using depth-weighted averaging.

    Intended layers:

        0-5 cm
        5-15 cm
        15-30 cm

    Thicknesses:

        5 cm
        10 cm
        15 cm

    Therefore deeper layers contribute proportionally
    according to their represented soil thickness.
    """

    if not layers:

        raise RootZoneSoilError(
            "No soil layers were provided."
        )


    for layer in layers:

        _validate_layer(
            layer
        )


    total_thickness = sum(

        (
            layer.depth_bottom_cm
            - layer.depth_top_cm
        )

        for layer in layers
    )


    if total_thickness <= 0:

        raise RootZoneSoilError(
            "Total soil depth must be positive."
        )


    def weighted_average(
        attribute: str,
    ) -> float:

        weighted_sum = 0.0


        for layer in layers:

            thickness = (
                layer.depth_bottom_cm
                - layer.depth_top_cm
            )


            weighted_sum += (
                getattr(
                    layer,
                    attribute,
                )
                * thickness
            )


        return round(
            weighted_sum
            / total_thickness,
            2,
        )


    soil_ph = weighted_average(
        "soil_ph"
    )

    sand_percent = weighted_average(
        "sand_percent"
    )

    silt_percent = weighted_average(
        "silt_percent"
    )

    clay_percent = weighted_average(
        "clay_percent"
    )


    components = {
        "sand": sand_percent,
        "silt": silt_percent,
        "clay": clay_percent,
    }


    dominant_component = max(
        components,
        key=components.get,
    )


    return RootZoneSoilContext(

        depth_top_cm=min(
            layer.depth_top_cm
            for layer in layers
        ),

        depth_bottom_cm=max(
            layer.depth_bottom_cm
            for layer in layers
        ),

        soil_ph=soil_ph,

        sand_percent=sand_percent,

        silt_percent=silt_percent,

        clay_percent=clay_percent,

        dominant_texture_component=(
            dominant_component
        ),

        source="SoilGrids root-zone aggregation",
    )
