from app.data.growth_stage import (
    validate_growth_stage_columns,
    validate_growth_stage_row,
)


VALID_ROW = {
    "crop": "Rice",
    "pest": "Blast; Sheath blight",
    "active_ingredient": "Kresoxim-methyl",
    "allowed_stages": "vegetative;reproductive",
    "application_timing": (
        "Early vegetative to reproductive stage"
    ),
    "source_document": "Official pesticide label",
    "source_page": "1",
    "source_url": "https://example.com/source.pdf",
    "source_date": "2026-01-01",
    "verified": "yes",
}


def test_valid_columns():

    valid, missing = (
        validate_growth_stage_columns(
            list(VALID_ROW.keys())
        )
    )

    assert valid is True
    assert missing == []


def test_verified_row_accepted():

    result = validate_growth_stage_row(
        VALID_ROW
    )

    assert result.status == "accepted"


def test_unverified_row_pending():

    row = dict(VALID_ROW)
    row["verified"] = "no"

    result = validate_growth_stage_row(
        row
    )

    assert result.status == "pending"


def test_invalid_stage_rejected():

    row = dict(VALID_ROW)

    row["allowed_stages"] = (
        "vegetative;unknown_stage"
    )

    result = validate_growth_stage_row(
        row
    )

    assert result.status == "rejected"

    assert (
        result.reason
        == "invalid_growth_stage"
    )


def test_flowering_normalized():

    row = dict(VALID_ROW)

    row["allowed_stages"] = (
        "vegetative;flowering"
    )

    result = validate_growth_stage_row(
        row
    )

    assert result.status == "accepted"

    assert (
        result.row["allowed_stages"]
        == "vegetative;reproductive"
    )


def test_missing_timing_rejected():

    row = dict(VALID_ROW)

    row["application_timing"] = ""

    result = validate_growth_stage_row(
        row
    )

    assert result.status == "rejected"

    assert (
        result.reason
        == "missing_application_timing"
    )


def test_missing_source_rejected():

    row = dict(VALID_ROW)

    row["source_document"] = ""

    result = validate_growth_stage_row(
        row
    )

    assert result.status == "rejected"


def test_missing_source_date_rejected():

    row = dict(VALID_ROW)

    row["source_date"] = ""

    result = validate_growth_stage_row(
        row
    )

    assert result.status == "rejected"
