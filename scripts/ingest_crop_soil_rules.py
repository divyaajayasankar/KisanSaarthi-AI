import csv
from pathlib import Path

from app.db import (
    Base,
    SessionLocal,
    engine,
)

from app.models_crop_soil import (
    CropSoilRule,
)


# ============================================================
# INPUT FILE
# ============================================================

INPUT_FILE = Path(
    "data/crop_soil/accepted_verified.csv"
)


# ============================================================
# BOOLEAN PARSER
# ============================================================

def parse_bool(
    value: str,
) -> bool:

    return str(
        value
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)

    print(
        "INGEST VERIFIED CROP-SOIL RULES"
    )

    print("=" * 70)


    # --------------------------------------------------------
    # Ensure table exists
    # --------------------------------------------------------

    Base.metadata.create_all(
        bind=engine
    )


    # --------------------------------------------------------
    # Check input
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"File not found: {INPUT_FILE}"
        )


    db = SessionLocal()


    inserted = 0

    skipped = 0


    try:

        with INPUT_FILE.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            reader = csv.DictReader(
                file
            )


            for row in reader:

                crop = row[
                    "crop"
                ].strip()


                source_document = row[
                    "source_document"
                ].strip()


                source_page = int(
                    row[
                        "source_page"
                    ]
                )


                # =================================================
                # ONLY VERIFIED RULES
                # =================================================

                verified = parse_bool(
                    row[
                        "verified"
                    ]
                )


                if not verified:

                    print(
                        f"Skipping unverified rule: {crop}"
                    )

                    skipped += 1

                    continue


                # =================================================
                # DUPLICATE CHECK
                # =================================================

                existing = (
                    db.query(
                        CropSoilRule
                    )
                    .filter(
                        CropSoilRule.crop
                        == crop,

                        CropSoilRule.source_document
                        == source_document,

                        CropSoilRule.source_page
                        == source_page,
                    )
                    .first()
                )


                if existing:

                    print(
                        f"Duplicate skipped: {crop}"
                    )

                    skipped += 1

                    continue


                # =================================================
                # CREATE DATABASE ROW
                # =================================================

                preferred_texture = (
                    row.get(
                        "preferred_texture",
                        "",
                    ).strip()
                )


                source_date = (
                    row.get(
                        "source_date",
                        "",
                    ).strip()
                )


                rule = CropSoilRule(

                    crop=crop,

                    min_ph=float(
                        row[
                            "min_ph"
                        ]
                    ),

                    max_ph=float(
                        row[
                            "max_ph"
                        ]
                    ),

                    preferred_texture=(
                        preferred_texture
                        if preferred_texture
                        else None
                    ),

                    source_document=(
                        source_document
                    ),

                    source_page=(
                        source_page
                    ),

                    source_url=(
                        row[
                            "source_url"
                        ].strip()
                    ),

                    source_date=(
                        source_date
                        if source_date
                        else None
                    ),

                    verified=True,
                )


                db.add(
                    rule
                )


                inserted += 1


        db.commit()


        print()

        print(
            f"Inserted verified rules : {inserted}"
        )

        print(
            f"Skipped rows            : {skipped}"
        )

        print()

        print(
            "Crop-soil ingestion complete."
        )


    except Exception:

        db.rollback()

        raise


    finally:

        db.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
