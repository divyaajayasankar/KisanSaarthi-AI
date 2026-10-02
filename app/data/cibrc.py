from typing import Any


REQUIRED_COLUMNS = [
    "crop",
    "pest",
    "active_ingredient",
    "formulation",
    "dose_min_per_hectare",
    "dose_max_per_hectare",
    "dose_unit",
    "water_volume_l_per_ha",
    "phi_days",
    "source_document",
    "source_page",
    "source_url",
    "source_date",
    "verified",
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).strip().split())


def parse_boolean(value: Any) -> bool:
    text = clean_text(value).lower()

    return text in {
        "1",
        "true",
        "yes",
        "y",
    }


def validate_registry_row(
    row: dict,
) -> tuple[str, dict, str]:

    cleaned = {
        key: clean_text(row.get(key))
        for key in REQUIRED_COLUMNS
    }

    # ========================================================
    # 1. REQUIRED TEXT FIELDS
    # ========================================================

    required_text = [
        "crop",
        "pest",
        "active_ingredient",
        "dose_unit",
        "source_document",
        "source_url",
    ]

    for field in required_text:

        if not cleaned[field]:

            return (
                "rejected",
                cleaned,
                f"missing_{field}",
            )

    # ========================================================
    # 2. DOSE MINIMUM
    # ========================================================

    try:
        dose_min = float(
            cleaned["dose_min_per_hectare"]
        )

    except (TypeError, ValueError):

        return (
            "rejected",
            cleaned,
            "dose_min_not_numeric",
        )

    if dose_min <= 0:

        return (
            "rejected",
            cleaned,
            "dose_min_not_positive",
        )

    # ========================================================
    # 3. DOSE MAXIMUM
    # ========================================================

    try:
        dose_max = float(
            cleaned["dose_max_per_hectare"]
        )

    except (TypeError, ValueError):

        return (
            "rejected",
            cleaned,
            "dose_max_not_numeric",
        )

    if dose_max <= 0:

        return (
            "rejected",
            cleaned,
            "dose_max_not_positive",
        )

    # Maximum cannot be smaller than minimum.

    if dose_max < dose_min:

        return (
            "rejected",
            cleaned,
            "dose_range_invalid",
        )

    # ========================================================
    # 4. PHI / WAITING PERIOD
    # ========================================================

    if cleaned["phi_days"] == "":

        return (
            "rejected",
            cleaned,
            "phi_missing",
        )

    try:
        phi = int(
            float(
                cleaned["phi_days"]
            )
        )

    except (TypeError, ValueError):

        return (
            "rejected",
            cleaned,
            "phi_not_numeric",
        )

    if phi < 0:

        return (
            "rejected",
            cleaned,
            "phi_negative",
        )

    if phi > 120:

        return (
            "rejected",
            cleaned,
            "phi_implausible",
        )

    # ========================================================
    # 5. SOURCE PAGE
    # ========================================================

    try:
        source_page = int(
            cleaned["source_page"]
        )

    except (TypeError, ValueError):

        return (
            "rejected",
            cleaned,
            "source_page_invalid",
        )

    if source_page <= 0:

        return (
            "rejected",
            cleaned,
            "source_page_invalid",
        )

    # ========================================================
    # 6. OFFICIAL PPQS SOURCE
    # ========================================================

    source_url = (
        cleaned["source_url"]
        .lower()
    )

    if "ppqs.gov.in" not in source_url:

        return (
            "rejected",
            cleaned,
            "non_ppqs_source",
        )

    # ========================================================
    # 7. OPTIONAL WATER VOLUME
    # ========================================================

    water = cleaned[
        "water_volume_l_per_ha"
    ]

    if water:

        try:
            water_value = float(water)

        except (TypeError, ValueError):

            return (
                "rejected",
                cleaned,
                "water_volume_invalid",
            )

        if water_value <= 0:

            return (
                "rejected",
                cleaned,
                "water_volume_invalid",
            )

    # ========================================================
    # 8. MANUAL VERIFICATION
    # ========================================================

    if not parse_boolean(
        cleaned["verified"]
    ):

        return (
            "pending",
            cleaned,
            "manual_verification_required",
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    return (
        "accepted",
        cleaned,
        "ok",
    )