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


def clean_text(
    value: str | None,
) -> str:
    if value is None:
        return ""

    return value.strip()


def parse_float(
    value: str | None,
) -> float | None:
    value = clean_text(value)

    if not value:
        return None

    return float(value)


def parse_int(
    value: str | None,
) -> int | None:
    value = clean_text(value)

    if not value:
        return None

    return int(float(value))


def parse_bool(
    value: str | None,
) -> bool:
    return (
        clean_text(value).lower()
        in {
            "true",
            "1",
            "yes",
            "y",
        }
    )


def normalize_dose_unit(
    value: str,
) -> str:
    """
    Existing constraint engine expects units such as:

        ml
        g
        kg

    rather than:

        ml/ha
        g/ha
        kg/ha
    """

    unit = clean_text(value)

    unit = (
        unit
        .replace("/hectare", "")
        .replace("/ha", "")
        .strip()
    )

    return unit


def get_exact_water_volume(
    row: dict,
) -> float | None:
    """
    Existing RegistryEntry has only one water-volume field.

    If the source provides one exact value, store it.

    If the source provides a range, do not invent an
    average value. Store None instead.
    """

    minimum = parse_float(
        row.get(
            "water_min_l_ha"
        )
    )

    maximum = parse_float(
        row.get(
            "water_max_l_ha"
        )
    )

    if (
        minimum is None
        and
        maximum is None
    ):
        return None

    if (
        minimum is not None
        and
        maximum is not None
        and
        minimum == maximum
    ):
        return minimum

    if (
        minimum is not None
        and
        maximum is None
    ):
        return minimum

    if (
        maximum is not None
        and
        minimum is None
    ):
        return maximum

    # A range cannot be represented accurately
    # by the current RegistryEntry schema.
    return None


if not INPUT.exists():
    raise FileNotFoundError(
        f"15-crop registry file not found: {INPUT}"
    )


inserted = 0
skipped_duplicate = 0
skipped_unverified = 0
skipped_phi_not_applicable = 0
skipped_invalid = 0


with SessionLocal() as db:

    with INPUT.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            crop = clean_text(
                row.get("crop")
            )

            pest = clean_text(
                row.get("pest")
            )

            active_ingredient = clean_text(
                row.get(
                    "active_ingredient"
                )
            )

            formulation = clean_text(
                row.get(
                    "formulation"
                )
            )

            verified = parse_bool(
                row.get("verified")
            )

            phi_required = parse_bool(
                row.get(
                    "phi_required"
                )
            )

            # ---------------------------------------------
            # Only verified seed records are accepted
            # ---------------------------------------------

            if not verified:

                skipped_unverified += 1

                print(
                    f"SKIP unverified: "
                    f"{crop} | {pest}"
                )

                continue


            # ---------------------------------------------
            # Current DB requires numeric PHI.
            #
            # Never convert "PHI not applicable" into
            # an invented numeric waiting period.
            # ---------------------------------------------

            if not phi_required:

                skipped_phi_not_applicable += 1

                print(
                    f"SKIP PHI-N/A: "
                    f"{crop} | {pest}"
                )

                continue


            phi_days = parse_int(
                row.get(
                    "phi_days"
                )
            )


            dose_min = parse_float(
                row.get(
                    "dose_min_per_ha"
                )
            )

            dose_max = parse_float(
                row.get(
                    "dose_max_per_ha"
                )
            )


            if (
                not crop
                or
                not pest
                or
                not active_ingredient
                or
                dose_min is None
                or
                dose_max is None
                or
                phi_days is None
            ):

                skipped_invalid += 1

                print(
                    f"SKIP invalid record: "
                    f"{crop} | {pest}"
                )

                continue


            dose_unit = normalize_dose_unit(
                row.get(
                    "dose_unit",
                    "",
                )
            )


            if not dose_unit:

                skipped_invalid += 1

                print(
                    f"SKIP missing dose unit: "
                    f"{crop} | {pest}"
                )

                continue


            # ---------------------------------------------
            # Do not create duplicate working registry rows
            # ---------------------------------------------

            existing = (
                db.query(
                    RegistryEntry
                )
                .filter(
                    RegistryEntry.crop
                    .ilike(crop),

                    RegistryEntry.pest
                    .ilike(pest),

                    RegistryEntry.active_ingredient
                    .ilike(active_ingredient),

                    RegistryEntry.is_test_data
                    .is_(False),
                )
                .first()
            )


            if existing:

                skipped_duplicate += 1

                print(
                    f"SKIP existing: "
                    f"{crop} | {pest} | "
                    f"{active_ingredient}"
                )

                continue


            source_name = clean_text(
                row.get(
                    "source_name"
                )
            )

            source_url = clean_text(
                row.get(
                    "source_url"
                )
            )


            # ---------------------------------------------
            # source_page = 0 is a TECHNICAL SENTINEL.
            #
            # It means the seed CSV stores the official
            # source URL but has not encoded an exact PDF
            # page number.
            #
            # Do not report page 0 as a real source page.
            # ---------------------------------------------

            registry_entry = (
                RegistryEntry(
                    crop=crop,

                    pest=pest,

                    active_ingredient=(
                        active_ingredient
                    ),

                    formulation=(
                        formulation
                        or None
                    ),

                    dose_min_per_hectare=(
                        dose_min
                    ),

                    dose_max_per_hectare=(
                        dose_max
                    ),

                    dose_unit=(
                        dose_unit
                    ),

                    water_volume_l_per_ha=(
                        get_exact_water_volume(
                            row
                        )
                    ),

                    phi_days=(
                        phi_days
                    ),

                    source_document=(
                        source_name
                        or
                        "Official PPQS/CIB&RC source"
                    ),

                    source_page=0,

                    source_url=(
                        source_url
                    ),

                    source_date=None,

                    verified=True,

                    is_test_data=False,
                )
            )


            db.add(
                registry_entry
            )

            inserted += 1


    db.commit()


print()
print("=" * 60)
print(
    "KisanSaarthi 15-Crop Registry Import"
)
print("=" * 60)

print(
    f"Inserted                 : {inserted}"
)

print(
    f"Existing duplicates      : {skipped_duplicate}"
)

print(
    f"Unverified skipped       : {skipped_unverified}"
)

print(
    f"PHI not applicable       : {skipped_phi_not_applicable}"
)

print(
    f"Invalid rows skipped     : {skipped_invalid}"
)

print("=" * 60)

print(
    "NOTE: PHI-N/A crops are intentionally not inserted "
    "until explicit PHI-not-applicable support is added."
)