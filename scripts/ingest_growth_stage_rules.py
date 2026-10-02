import csv
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models_growth_stage import GrowthStageRule


INPUT_FILE = Path(
    "data/growth_stage/accepted_verified.csv"
)


def parse_bool(value) -> bool:

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def main():

    print("=" * 70)
    print("INGESTING VERIFIED GROWTH-STAGE RULES")
    print("=" * 70)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"File not found: {INPUT_FILE}"
        )

    # Create table if it does not already exist
    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:

        with INPUT_FILE.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            reader = csv.DictReader(file)
            rows = list(reader)

        verified_rows = [
            row
            for row in rows
            if parse_bool(
                row.get("verified")
            )
        ]

        # Safe for prototype:
        # replace only the growth-stage rule table contents.
        db.query(
            GrowthStageRule
        ).delete()

        for row in verified_rows:

            record = GrowthStageRule(
                crop=row["crop"].strip(),
                pest=row["pest"].strip(),
                active_ingredient=(
                    row["active_ingredient"].strip()
                ),
                allowed_stages=(
                    row["allowed_stages"].strip()
                ),
                application_timing=(
                    row["application_timing"].strip()
                ),
                source_document=(
                    row["source_document"].strip()
                ),
                source_page=int(
                    row["source_page"]
                ),
                source_url=(
                    row["source_url"].strip()
                ),
                source_date=(
                    row["source_date"].strip()
                ),
                verified=True,
            )

            db.add(record)

        db.commit()

        count = (
            db.query(GrowthStageRule)
            .filter(
                GrowthStageRule.verified.is_(True)
            )
            .count()
        )

        print()
        print(
            f"Input verified rows : {len(verified_rows)}"
        )

        print(
            f"Database rows       : {count}"
        )

        print()
        print(
            "Growth-stage ingestion complete."
        )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()