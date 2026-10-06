import csv
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

REGISTRY_FILE = (
    PROJECT_ROOT
    / "data"
    / "registry"
    / "crop_registry_15.csv"
)


EXPECTED_CROPS = {
    "Rice",
    "Wheat",
    "Maize",
    "Tomato",
    "Chilli",
    "Brinjal",
    "Onion",
    "Potato",
    "Okra",
    "Cabbage",
    "Groundnut",
    "Chickpea",
    "Mustard",
    "Cotton",
    "Banana",
}


def load_rows():

    with REGISTRY_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        return list(
            csv.DictReader(file)
        )


def test_registry_file_exists():

    assert REGISTRY_FILE.exists()


def test_exactly_15_crop_records():

    rows = load_rows()

    assert len(rows) == 15


def test_expected_15_crops_present():

    rows = load_rows()

    crops = {
        row["crop"]
        for row in rows
    }

    assert crops == EXPECTED_CROPS


def test_all_records_verified():

    rows = load_rows()

    for row in rows:

        assert (
            row["verified"]
            .strip()
            .lower()
            ==
            "true"
        )


def test_all_records_have_positive_dose():

    rows = load_rows()

    for row in rows:

        minimum = float(
            row["dose_min_per_ha"]
        )

        maximum = float(
            row["dose_max_per_ha"]
        )

        assert minimum > 0
        assert maximum > 0
        assert maximum >= minimum


def test_phi_present_when_required():

    rows = load_rows()

    for row in rows:

        phi_required = (
            row["phi_required"]
            .strip()
            .lower()
            ==
            "true"
        )

        if phi_required:

            assert row["phi_days"].strip()

            assert (
                int(row["phi_days"])
                >=
                0
            )


def test_all_records_have_source():

    rows = load_rows()

    for row in rows:

        assert row["source_name"].strip()

        assert (
            row["source_url"]
            .strip()
            .startswith("https://")
        )


def test_all_records_have_moa():

    rows = load_rows()

    for row in rows:

        assert row["moa_system"].strip()
        assert row["moa_group"].strip()


def test_banana_phi_not_required():

    rows = load_rows()

    banana = next(
        row
        for row in rows
        if row["crop"] == "Banana"
    )

    assert (
        banana["phi_required"]
        .lower()
        ==
        "false"
    )

    assert banana["phi_days"] == ""


def test_groundnut_sowing_stage():

    rows = load_rows()

    groundnut = next(
        row
        for row in rows
        if row["crop"] == "Groundnut"
    )

    assert (
        groundnut[
            "allowed_growth_stages"
        ]
        ==
        "sowing"
    )

    assert (
        groundnut[
            "max_applications"
        ]
        ==
        "1"
    )
