from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

FILE_PATH = (
    PROJECT_ROOT
    / "data"
    / "growth_stage"
    / "growth_stage_rules.csv"
)


BANANA_RULE = {
    "crop": "Banana",

    "pest": "Sigatoka",

    "active_ingredient": "Bacillus subtilis",

    "allowed_stages": (
        "vegetative;reproductive"
    ),

    "application_timing": (
        "Foliar spray on disease incidence during "
        "vegetative/reproductive phase of the crop"
    ),

    "source_document": (
        "PPQS Bacillus subtilis 1.50% Liquid "
        "Formulation Primary Package Label"
    ),

    # Technical sentinel because the exact PDF page
    # is not encoded in the current project data.
    "source_page": "0",

    "source_url": (
        "https://ppqs.gov.in/sites/default/files/"
        "bacillus_subtilis_1.50_liquid_formulation_"
        "t_stanes_bs-1_strain_accession_no._"
        "mtcc_25072_1.pdf"
    ),

    "source_date": "2026-09-20",

    "verified": "true",
}


FIELDNAMES = [
    "crop",
    "pest",
    "active_ingredient",
    "allowed_stages",
    "application_timing",
    "source_document",
    "source_page",
    "source_url",
    "source_date",
    "verified",
]


def normalize(
    value: str | None,
) -> str:

    if not value:
        return ""

    return value.strip().lower()


if not FILE_PATH.exists():

    raise FileNotFoundError(
        f"Growth-stage rules file not found: {FILE_PATH}"
    )


with FILE_PATH.open(
    "r",
    newline="",
    encoding="utf-8-sig",
) as file:

    existing_rows = list(
        csv.DictReader(file)
    )


duplicate = False


for row in existing_rows:

    if (
        normalize(
            row.get("crop")
        )
        ==
        "banana"

        and

        normalize(
            row.get("pest")
        )
        ==
        "sigatoka"

        and

        normalize(
            row.get(
                "active_ingredient"
            )
        )
        ==
        "bacillus subtilis"
    ):

        duplicate = True
        break


if duplicate:

    print(
        "Banana growth-stage rule already exists."
    )


else:

    existing_rows.append(
        BANANA_RULE
    )

    with FILE_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()

        writer.writerows(
            existing_rows
        )


    print(
        "Added verified Banana growth-stage rule."
    )


print()
print("Crop              : Banana")
print("Pest              : Sigatoka")
print("Active ingredient : Bacillus subtilis")
print(
    "Allowed stages    : vegetative;reproductive"
)
print("Verified          : true")
