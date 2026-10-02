import csv
from pathlib import Path

from app.data.crop_soil import (
    REQUIRED_COLUMNS,
    validate_crop_soil_columns,
    validate_crop_soil_row,
)


# ============================================================
# FILE PATHS
# ============================================================

INPUT_FILE = Path(
    "data/crop_soil/crop_soil_rules.csv"
)

ACCEPTED_FILE = Path(
    "data/crop_soil/accepted_verified.csv"
)

PENDING_FILE = Path(
    "data/crop_soil/pending_verification.csv"
)

REJECTED_FILE = Path(
    "data/crop_soil/rejected.csv"
)


# ============================================================
# OUTPUT FIELDNAMES
# ============================================================

OUTPUT_FIELDS = [
    "crop",
    "min_ph",
    "max_ph",
    "preferred_texture",
    "source_document",
    "source_page",
    "source_url",
    "source_date",
    "verified",
]


REJECTED_FIELDS = (
    OUTPUT_FIELDS
    + ["validation_errors"]
)


# ============================================================
# WRITE CSV
# ============================================================

def write_csv(
    path: Path,
    rows: list[dict],
    fieldnames: list[str],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


# ============================================================
# MAIN VALIDATION
# ============================================================

def main():

    print("=" * 70)

    print(
        "CROP-SOIL RULE VALIDATION"
    )

    print("=" * 70)


    # ========================================================
    # INPUT FILE CHECK
    # ========================================================

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input file not found: "
            f"{INPUT_FILE}"
        )


    # ========================================================
    # READ INPUT
    # ========================================================

    with INPUT_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(
            file
        )


        if reader.fieldnames is None:

            raise ValueError(
                "CSV file has no header."
            )


        # ====================================================
        # REQUIRED COLUMN CHECK
        # ====================================================

        missing_columns = (
            validate_crop_soil_columns(
                reader.fieldnames
            )
        )


        if missing_columns:

            raise ValueError(
                "Missing required columns: "
                + ", ".join(
                    missing_columns
                )
            )


        rows = list(
            reader
        )


    print(
        f"Input rows: {len(rows)}"
    )


    # ========================================================
    # VALIDATE ROWS
    # ========================================================

    accepted_rows = []

    pending_rows = []

    rejected_rows = []


    for row_number, row in enumerate(
        rows,
        start=2,
    ):

        result = (
            validate_crop_soil_row(
                row
            )
        )


        # ====================================================
        # ACCEPTED
        # ====================================================

        if result.status == "accepted":

            accepted_rows.append(
                result.normalized_row
            )


        # ====================================================
        # PENDING
        # ====================================================

        elif result.status == "pending":

            pending_rows.append(
                result.normalized_row
            )


        # ====================================================
        # REJECTED
        # ====================================================

        else:

            rejected_row = {
                field: row.get(
                    field,
                    "",
                )
                for field in OUTPUT_FIELDS
            }


            rejected_row[
                "validation_errors"
            ] = "; ".join(
                result.errors
            )


            rejected_rows.append(
                rejected_row
            )


            print(
                f"Rejected row "
                f"{row_number}: "
                f"{result.errors}"
            )


    # ========================================================
    # WRITE OUTPUTS
    # ========================================================

    write_csv(
        ACCEPTED_FILE,
        accepted_rows,
        OUTPUT_FIELDS,
    )


    write_csv(
        PENDING_FILE,
        pending_rows,
        OUTPUT_FIELDS,
    )


    write_csv(
        REJECTED_FILE,
        rejected_rows,
        REJECTED_FIELDS,
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    print()

    print(
        f"Accepted verified rows : "
        f"{len(accepted_rows)}"
    )

    print(
        f"Pending verification   : "
        f"{len(pending_rows)}"
    )

    print(
        f"Rejected rows           : "
        f"{len(rejected_rows)}"
    )


    print()

    print(
        f"Accepted file : "
        f"{ACCEPTED_FILE}"
    )

    print(
        f"Pending file  : "
        f"{PENDING_FILE}"
    )

    print(
        f"Rejected file : "
        f"{REJECTED_FILE}"
    )


    print()

    print(
        "Crop-soil validation complete."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()