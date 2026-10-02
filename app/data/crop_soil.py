from dataclasses import dataclass
from typing import Any


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS = {
    "crop",
    "min_ph",
    "max_ph",
    "preferred_texture",
    "source_document",
    "source_page",
    "source_url",
    "source_date",
    "verified",
}


# ============================================================
# VALIDATION RESULT
# ============================================================

@dataclass
class CropSoilValidationResult:
    status: str
    normalized_row: dict[str, Any] | None
    errors: list[str]


# ============================================================
# VERIFIED FLAG PARSER
# ============================================================

def _parse_verified(value: Any) -> bool:

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


# ============================================================
# VALIDATE CSV COLUMNS
# ============================================================

def validate_crop_soil_columns(
    columns: list[str],
) -> list[str]:

    missing = sorted(
        REQUIRED_COLUMNS
        - set(columns)
    )

    return missing


# ============================================================
# VALIDATE ONE CROP-SOIL RULE
# ============================================================

def validate_crop_soil_row(
    row: dict[str, Any],
) -> CropSoilValidationResult:
    """
    Validate one crop-soil suitability rule.

    This function NEVER guesses or repairs missing
    agricultural values.

    Invalid evidence -> rejected
    Unverified evidence -> pending
    Verified valid evidence -> accepted
    """

    errors: list[str] = []


    # ========================================================
    # CROP
    # ========================================================

    crop = str(
        row.get(
            "crop",
            "",
        )
    ).strip()


    if not crop:
        errors.append(
            "crop is required"
        )


    # ========================================================
    # MINIMUM PH
    # ========================================================

    min_ph = None

    try:

        min_ph = float(
            row.get(
                "min_ph"
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        errors.append(
            "min_ph must be numeric"
        )


    # ========================================================
    # MAXIMUM PH
    # ========================================================

    max_ph = None

    try:

        max_ph = float(
            row.get(
                "max_ph"
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        errors.append(
            "max_ph must be numeric"
        )


    # ========================================================
    # PH RANGE VALIDATION
    # ========================================================

    if min_ph is not None:

        if not 0 < min_ph <= 14:

            errors.append(
                "min_ph must be greater than 0 "
                "and at most 14"
            )


    if max_ph is not None:

        if not 0 < max_ph <= 14:

            errors.append(
                "max_ph must be greater than 0 "
                "and at most 14"
            )


    if (
        min_ph is not None
        and max_ph is not None
        and max_ph < min_ph
    ):

        errors.append(
            "max_ph must be greater than "
            "or equal to min_ph"
        )


    # ========================================================
    # PREFERRED TEXTURE
    # ========================================================

    preferred_texture = str(
        row.get(
            "preferred_texture",
            "",
        )
    ).strip()

    # Blank is permitted because some authoritative
    # documents may specify pH but not texture.


    # ========================================================
    # SOURCE DOCUMENT
    # ========================================================

    source_document = str(
        row.get(
            "source_document",
            "",
        )
    ).strip()


    if not source_document:

        errors.append(
            "source_document is required"
        )


    # ========================================================
    # SOURCE PAGE
    # ========================================================

    source_page = None

    source_page_raw = str(
        row.get(
            "source_page",
            "",
        )
    ).strip()


    if not source_page_raw:

        errors.append(
            "source_page is required"
        )

    else:

        try:

            source_page = int(
                source_page_raw
            )


            if source_page <= 0:

                errors.append(
                    "source_page must be positive"
                )


        except ValueError:

            errors.append(
                "source_page must be an integer"
            )


    # ========================================================
    # SOURCE URL
    # ========================================================

    source_url = str(
        row.get(
            "source_url",
            "",
        )
    ).strip()


    if not source_url:

        errors.append(
            "source_url is required"
        )


    # ========================================================
    # SOURCE DATE
    # ========================================================

    source_date = str(
        row.get(
            "source_date",
            "",
        )
    ).strip()

    # Source date may be blank for older official documents.


    # ========================================================
    # VERIFIED
    # ========================================================

    verified = _parse_verified(
        row.get(
            "verified",
            "",
        )
    )


    # ========================================================
    # INVALID -> REJECT
    # ========================================================

    if errors:

        return CropSoilValidationResult(
            status="rejected",
            normalized_row=None,
            errors=errors,
        )


    # ========================================================
    # NORMALIZED RULE
    # ========================================================

    normalized_row = {

        "crop": crop,

        "min_ph": min_ph,

        "max_ph": max_ph,

        "preferred_texture": (
            preferred_texture
        ),

        "source_document": (
            source_document
        ),

        "source_page": (
            source_page
        ),

        "source_url": (
            source_url
        ),

        "source_date": (
            source_date
        ),

        "verified": verified,
    }


    # ========================================================
    # UNVERIFIED -> PENDING
    # ========================================================

    if not verified:

        return CropSoilValidationResult(
            status="pending",
            normalized_row=normalized_row,
            errors=[],
        )


    # ========================================================
    # VERIFIED -> ACCEPTED
    # ========================================================

    return CropSoilValidationResult(
        status="accepted",
        normalized_row=normalized_row,
        errors=[],
    )