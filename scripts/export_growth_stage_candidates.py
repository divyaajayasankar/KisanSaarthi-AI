import csv
from pathlib import Path

from app.db import SessionLocal
from app.models import RegistryEntry


OUTPUT_FILE = Path(
    "data/growth_stage/registry_candidates.csv"
)


def main():

    print("=" * 70)
    print("EXPORTING GROWTH-STAGE CANDIDATES")
    print("=" * 70)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    db = SessionLocal()

    try:

        rows = (
            db.query(RegistryEntry)
            .filter(
                RegistryEntry.verified.is_(True),
                RegistryEntry.is_test_data.is_(False),
            )
            .order_by(
                RegistryEntry.crop,
                RegistryEntry.pest,
            )
            .all()
        )

        fieldnames = [
            "registry_id",
            "crop",
            "pest",
            "active_ingredient",
            "phi_days",
            "restricted_stage",
            "restriction_reason",
            "source_document",
            "source_page",
            "source_url",
            "source_date",
            "verified",
        ]

        with OUTPUT_FILE.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            for row in rows:

                writer.writerow(
                    {
                        "registry_id": row.id,
                        "crop": row.crop,
                        "pest": row.pest,
                        "active_ingredient": row.active_ingredient,
                        "phi_days": row.phi_days,

                        # Leave these empty until verified
                        "restricted_stage": "",
                        "restriction_reason": "",
                        "source_document": "",
                        "source_page": "",
                        "source_url": "",
                        "source_date": "",
                        "verified": "false",
                    }
                )

        print(
            f"Verified registry rows : {len(rows)}"
        )

        print(
            f"Saved file             : {OUTPUT_FILE}"
        )

        print()
        print(
            "Growth-stage candidate export complete."
        )

    finally:

        db.close()


if __name__ == "__main__":
    main()
