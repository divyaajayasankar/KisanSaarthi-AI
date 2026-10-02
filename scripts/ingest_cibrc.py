import csv
from pathlib import Path

from app.db import SessionLocal
from app.models import RegistryEntry


INPUT = Path(
    "data/cibrc/accepted_verified.csv"
)


if not INPUT.exists():
    raise FileNotFoundError(
        "accepted_verified.csv not found. "
        "Run: python -m scripts.validate_cibrc_csv"
    )


inserted = 0
skipped = 0


with SessionLocal() as db:

    with INPUT.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            existing = (
                db.query(RegistryEntry)
                .filter_by(
                    crop=row["crop"],
                    pest=row["pest"],
                    active_ingredient=row["active_ingredient"],
                    formulation=row["formulation"] or None,
                    source_document=row["source_document"],
                    source_page=int(row["source_page"]),
                    is_test_data=False,
                )
                .first()
            )

            if existing:
                skipped += 1
                continue

            water = row["water_volume_l_per_ha"]

            registry_entry = RegistryEntry(
                crop=row["crop"],
                pest=row["pest"],

                active_ingredient=row[
                    "active_ingredient"
                ],

                formulation=(
                    row["formulation"]
                    or None
                ),

                dose_min_per_hectare=float(
                    row["dose_min_per_hectare"]
                ),

                dose_max_per_hectare=float(
                    row["dose_max_per_hectare"]
                ),

                dose_unit=row["dose_unit"],

                water_volume_l_per_ha=(
                    float(water)
                    if water
                    else None
                ),

                phi_days=int(
                    float(row["phi_days"])
                ),

                source_document=row[
                    "source_document"
                ],

                source_page=int(
                    row["source_page"]
                ),

                source_url=row[
                    "source_url"
                ],

                source_date=(
                    row["source_date"]
                    or None
                ),

                verified=True,
                is_test_data=False,
            )

            db.add(registry_entry)

            inserted += 1

    db.commit()


print(
    f"Inserted real verified rows: {inserted}"
)

print(
    f"Skipped duplicate rows     : {skipped}"
)