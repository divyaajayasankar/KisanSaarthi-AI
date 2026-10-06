from __future__ import annotations

import csv
from pathlib import Path

from app.db import SessionLocal
from app.models import RegistryEntry


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

INPUT = (
    PROJECT_ROOT
    / "data"
    / "registry"
    / "crop_registry_15.csv"
)


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


if not INPUT.exists():

    raise FileNotFoundError(
        f"Registry file not found: {INPUT}"
    )


banana = None


with INPUT.open(
    "r",
    newline="",
    encoding="utf-8-sig",
) as file:

    for row in csv.DictReader(file):

        if (
            clean(
                row.get("crop")
            ).lower()
            ==
            "banana"
        ):

            banana = row
            break


if banana is None:

    raise RuntimeError(
        "Banana row not found in crop_registry_15.csv"
    )


if (
    clean(
        banana.get(
            "phi_required"
        )
    ).lower()
    !=
    "false"
):

    raise RuntimeError(
        "Banana seed record is not marked "
        "PHI-not-applicable."
    )


dose_unit = (
    clean(
        banana.get(
            "dose_unit"
        )
    )
    .replace("/ha", "")
    .replace("/hectare", "")
    .strip()
)


water_min = clean(
    banana.get(
        "water_min_l_ha"
    )
)

water_max = clean(
    banana.get(
        "water_max_l_ha"
    )
)


water_volume = None


if (
    water_min
    and
    water_max
    and
    float(water_min)
    ==
    float(water_max)
):

    water_volume = float(
        water_min
    )


with SessionLocal() as db:

    existing = (
        db.query(
            RegistryEntry
        )
        .filter(
            RegistryEntry.crop.ilike(
                "Banana"
            ),

            RegistryEntry.pest.ilike(
                clean(
                    banana.get(
                        "pest"
                    )
                )
            ),

            RegistryEntry.active_ingredient.ilike(
                clean(
                    banana.get(
                        "active_ingredient"
                    )
                )
            ),

            RegistryEntry.is_test_data.is_(
                False
            ),
        )
        .first()
    )


    if existing:

        existing.phi_not_applicable = True

        # Technical storage sentinel only.
        # The constraint engine ignores this value
        # whenever phi_not_applicable=True.
        existing.phi_days = 0

        db.commit()

        print(
            "Updated existing Banana registry row."
        )


    else:

        record = RegistryEntry(
            crop="Banana",

            pest=clean(
                banana.get(
                    "pest"
                )
            ),

            active_ingredient=clean(
                banana.get(
                    "active_ingredient"
                )
            ),

            formulation=(
                clean(
                    banana.get(
                        "formulation"
                    )
                )
                or None
            ),

            dose_min_per_hectare=float(
                banana[
                    "dose_min_per_ha"
                ]
            ),

            dose_max_per_hectare=float(
                banana[
                    "dose_max_per_ha"
                ]
            ),

            dose_unit=dose_unit,

            water_volume_l_per_ha=(
                water_volume
            ),

            # Technical storage sentinel only.
            phi_days=0,

            phi_not_applicable=True,

            source_document=clean(
                banana.get(
                    "source_name"
                )
            ),

            # Exact PDF page was not encoded
            # in the seed CSV.
            source_page=0,

            source_url=clean(
                banana.get(
                    "source_url"
                )
            ),

            source_date=None,

            verified=True,

            is_test_data=False,
        )


        db.add(
            record
        )

        db.commit()

        print(
            "Inserted Banana PHI-N/A registry row."
        )
