import csv
import sys
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


# ============================================================
# PROJECT IMPORTS
# ============================================================

from app.db import (
    Base,
    SessionLocal,
    engine,
)

from app.models_treatment_history import (
    TreatmentHistoryRule,
)


# ============================================================
# CSV PATH
# ============================================================

CSV_PATH = (
    ROOT_DIR
    / "data"
    / "treatment_history"
    / "treatment_history_rules.csv"
)


# ============================================================
# HELPERS
# ============================================================

def clean_text(
    value,
):

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def parse_optional_int(
    value,
):

    value = clean_text(
        value
    )

    if value is None:
        return None

    return int(
        float(value)
    )


def parse_optional_float(
    value,
):

    value = clean_text(
        value
    )

    if value is None:
        return None

    return float(
        value
    )


def parse_bool(
    value,
):

    value = clean_text(
        value
    )

    if value is None:
        return False

    return value.lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


# ============================================================
# VALIDATE CSV ROW
# ============================================================

def validate_row(
    row,
    row_number,
):

    required_fields = [
        "crop",
        "pest",
        "active_ingredient",
        "history_scope",
        "source_document",
        "source_url",
    ]

    for field in required_fields:

        if not clean_text(
            row.get(field)
        ):

            raise ValueError(
                f"Row {row_number}: "
                f"missing required field '{field}'."
            )


    max_applications = (
        parse_optional_int(
            row.get(
                "max_applications"
            )
        )
    )

    if (
        max_applications is not None
        and max_applications <= 0
    ):

        raise ValueError(
            f"Row {row_number}: "
            "max_applications must be greater than 0."
        )


    min_interval_days = (
        parse_optional_float(
            row.get(
                "min_interval_days"
            )
        )
    )

    if (
        min_interval_days is not None
        and min_interval_days < 0
    ):

        raise ValueError(
            f"Row {row_number}: "
            "min_interval_days cannot be negative."
        )


# ============================================================
# INGEST
# ============================================================

def ingest():

    print(
        "\n[1] Checking CSV..."
    )

    if not CSV_PATH.exists():

        raise FileNotFoundError(
            f"CSV not found: {CSV_PATH}"
        )


    # --------------------------------------------------------
    # ENSURE TABLE EXISTS
    # --------------------------------------------------------

    print(
        "[2] Ensuring database table exists..."
    )

    Base.metadata.create_all(
        bind=engine
    )


    db = SessionLocal()

    inserted = 0
    updated = 0


    try:

        print(
            "[3] Reading treatment-history rules..."
        )


        with open(
            CSV_PATH,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(
                file
            )


            for row_number, row in enumerate(
                reader,
                start=2,
            ):

                validate_row(
                    row,
                    row_number,
                )


                crop = clean_text(
                    row.get(
                        "crop"
                    )
                )

                pest = clean_text(
                    row.get(
                        "pest"
                    )
                )

                active_ingredient = clean_text(
                    row.get(
                        "active_ingredient"
                    )
                )


                # ============================================
                # LOOK FOR EXISTING RULE
                # ============================================

                existing = (
                    db.query(
                        TreatmentHistoryRule
                    )
                    .filter(
                        TreatmentHistoryRule.crop.ilike(
                            crop
                        ),
                        TreatmentHistoryRule.pest.ilike(
                            pest
                        ),
                        TreatmentHistoryRule.active_ingredient.ilike(
                            active_ingredient
                        ),
                    )
                    .first()
                )


                values = {

                    "crop":
                        crop,

                    "pest":
                        pest,

                    "active_ingredient":
                        active_ingredient,

                    "max_applications":
                        parse_optional_int(
                            row.get(
                                "max_applications"
                            )
                        ),

                    "min_interval_days":
                        parse_optional_float(
                            row.get(
                                "min_interval_days"
                            )
                        ),

                    "history_scope":
                        clean_text(
                            row.get(
                                "history_scope"
                            )
                        ),

                    "application_stage":
                        clean_text(
                            row.get(
                                "application_stage"
                            )
                        ),

                    "verified":
                        parse_bool(
                            row.get(
                                "verified"
                            )
                        ),

                    "source_document":
                        clean_text(
                            row.get(
                                "source_document"
                            )
                        ),

                    "source_page":
                        parse_optional_int(
                            row.get(
                                "source_page"
                            )
                        ),

                    "source_url":
                        clean_text(
                            row.get(
                                "source_url"
                            )
                        ),

                    "notes":
                        clean_text(
                            row.get(
                                "notes"
                            )
                        ),
                }


                # ============================================
                # UPDATE EXISTING ROW
                # ============================================

                if existing is not None:

                    for (
                        field_name,
                        field_value,
                    ) in values.items():

                        setattr(
                            existing,
                            field_name,
                            field_value,
                        )

                    updated += 1


                # ============================================
                # INSERT NEW ROW
                # ============================================

                else:

                    rule = (
                        TreatmentHistoryRule(
                            **values
                        )
                    )

                    db.add(
                        rule
                    )

                    inserted += 1


        db.commit()


        print(
            "[4] Ingestion complete."
        )

        print(
            f"Inserted: {inserted}"
        )

        print(
            f"Updated:  {updated}"
        )


        # ----------------------------------------------------
        # DISPLAY VERIFIED DATABASE RULES
        # ----------------------------------------------------

        rules = (
            db.query(
                TreatmentHistoryRule
            )
            .order_by(
                TreatmentHistoryRule.id
            )
            .all()
        )


        print(
            f"\nTotal treatment-history rules: "
            f"{len(rules)}"
        )


        for rule in rules:

            print(
                "\n"
                f"ID: {rule.id}\n"
                f"Crop: {rule.crop}\n"
                f"Pest: {rule.pest}\n"
                f"Active ingredient: "
                f"{rule.active_ingredient}\n"
                f"Max applications: "
                f"{rule.max_applications}\n"
                f"Min interval days: "
                f"{rule.min_interval_days}\n"
                f"Scope: "
                f"{rule.history_scope}\n"
                f"Application stage: "
                f"{rule.application_stage}\n"
                f"Verified: "
                f"{rule.verified}"
            )


    except Exception:

        db.rollback()

        raise


    finally:

        db.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    ingest()