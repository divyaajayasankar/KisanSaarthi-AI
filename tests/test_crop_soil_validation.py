from app.data.crop_soil import (
    validate_crop_soil_columns,
    validate_crop_soil_row,
)


# ============================================================
# VALID TEST ROW
# ============================================================

def valid_row():

    return {

        "crop": "TestCrop",

        "min_ph": "5.5",

        "max_ph": "7.0",

        "preferred_texture": "loam",

        "source_document": (
            "official_crop_guide.pdf"
        ),

        "source_page": "10",

        "source_url": (
            "https://example.gov.in/"
            "official_crop_guide.pdf"
        ),

        "source_date": "2026-01-01",

        "verified": "yes",
    }


# ============================================================
# 1. VALID VERIFIED ROW
# ============================================================

def test_valid_verified_rule():

    result = validate_crop_soil_row(
        valid_row()
    )

    assert result.status == "accepted"

    assert (
        result.normalized_row[
            "min_ph"
        ]
        == 5.5
    )

    assert (
        result.normalized_row[
            "max_ph"
        ]
        == 7.0
    )


# ============================================================
# 2. UNVERIFIED ROW
# ============================================================

def test_unverified_rule_pending():

    row = valid_row()

    row["verified"] = "no"


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "pending"


# ============================================================
# 3. MISSING CROP
# ============================================================

def test_missing_crop_rejected():

    row = valid_row()

    row["crop"] = ""


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 4. INVALID MIN PH
# ============================================================

def test_invalid_min_ph_rejected():

    row = valid_row()

    row["min_ph"] = "abc"


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 5. INVALID MAX PH
# ============================================================

def test_invalid_max_ph_rejected():

    row = valid_row()

    row["max_ph"] = "20"


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 6. REVERSED PH RANGE
# ============================================================

def test_reversed_ph_range_rejected():

    row = valid_row()

    row["min_ph"] = "8"

    row["max_ph"] = "6"


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 7. MISSING SOURCE DOCUMENT
# ============================================================

def test_missing_source_document_rejected():

    row = valid_row()

    row["source_document"] = ""


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 8. INVALID SOURCE PAGE
# ============================================================

def test_invalid_source_page_rejected():

    row = valid_row()

    row["source_page"] = "0"


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 9. MISSING SOURCE URL
# ============================================================

def test_missing_source_url_rejected():

    row = valid_row()

    row["source_url"] = ""


    result = validate_crop_soil_row(
        row
    )


    assert result.status == "rejected"


# ============================================================
# 10. REQUIRED CSV COLUMN CHECK
# ============================================================

def test_missing_csv_column_detected():

    columns = [
        "crop",
        "min_ph",
        "max_ph",
        "preferred_texture",
        "source_document",
        "source_page",
        "source_url",
        "source_date",
    ]


    missing = validate_crop_soil_columns(
        columns
    )


    assert "verified" in missing