from app.services.crop_coverage_service import (
    get_all_configured_crops,
    get_crop_coverage,
    get_supported_crops,
)


def test_exactly_15_crops_configured():

    crops = get_all_configured_crops()

    assert len(crops) == 15


def test_rice_supported():

    result = get_crop_coverage(
        "Rice"
    )

    assert result["supported"] is True
    assert result["registry"] is True
    assert result["rag"] is True


def test_groundnut_supported():

    result = get_crop_coverage(
        "Groundnut"
    )

    assert result["supported"] is True


def test_wheat_partial_support():

    result = get_crop_coverage(
        "Wheat"
    )

    assert result["supported"] is False

    assert (
        result["status"]
        == "partial_support"
    )

    assert result["registry"] is True
    assert result["phi"] is True
    assert result["weather"] is True
    assert result["soil"] is True


def test_unknown_crop_unsupported():

    result = get_crop_coverage(
        "Unknown Crop"
    )

    assert result["supported"] is False

    assert (
        result["status"]
        == "unsupported"
    )


def test_case_insensitive():

    result = get_crop_coverage(
        "rice"
    )

    assert result["crop"] == "Rice"
    assert result["supported"] is True


def test_supported_crop_list():

    crops = get_supported_crops()

    assert "Rice" in crops
    assert "Groundnut" in crops
