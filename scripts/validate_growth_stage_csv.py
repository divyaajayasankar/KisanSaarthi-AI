import csv
from pathlib import Path

from app.data.growth_stage import (
    REQUIRED_COLUMNS,
    validate_growth_stage_columns,
    validate_growth_stage_row,
)


INPUT_FILE = Path(
    "data/growth_stage/growth_stage_rules.csv"
)

OUTPUT_DIR = Path(
    "data/growth_stage"
)

ACCEPTED_FILE = (
    OUTPUT_DIR
    / "accepted_verified.csv"
)

PENDING_FILE = (
    OUTPUT_DIR
    / "pending_verification.csv"
)

REJECTED_FILE = (
    OUTPUT_DIR
    / "rejected.csv"
)


def write_rows(
    path: Path,
    fieldnames: list[str],
    rows: list[dict],
):

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def main():

    print("=" * 70)
    print("GROWTH-STAGE RULE VALIDATION")
    print("=" * 70)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    accepted = []
    pending = []
    rejected = []

    with INPUT_FILE.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.DictReader(file)

        valid_columns, missing_columns = (
            validate_growth_stage_columns(
                reader.fieldnames
            )
        )

        if not valid_columns:

            raise ValueError(
                "Growth-stage CSV is missing required columns: "
                + ", ".join(missing_columns)
            )

        fieldnames = list(
            reader.fieldnames
        )

        rows = list(reader)

    for row in rows:

        result = validate_growth_stage_row(
            row
        )

        if result.status == "accepted":

            accepted.append(
                result.row
            )

        elif result.status == "pending":

            pending.append(
                result.row
            )

        else:

            rejected_row = dict(
                result.row
            )

            rejected_row[
                "rejection_reason"
            ] = result.reason

            rejected.append(
                rejected_row
            )

    write_rows(
        ACCEPTED_FILE,
        fieldnames,
        accepted,
    )

    write_rows(
        PENDING_FILE,
        fieldnames,
        pending,
    )

    rejected_fieldnames = (
        fieldnames
        + ["rejection_reason"]
    )

    write_rows(
        REJECTED_FILE,
        rejected_fieldnames,
        rejected,
    )

    print()
    print(
        f"Input rows               : {len(rows)}"
    )

    print(
        f"Accepted verified rows   : {len(accepted)}"
    )

    print(
        f"Pending verification     : {len(pending)}"
    )

    print(
        f"Rejected rows             : {len(rejected)}"
    )

    print()
    print(
        f"Accepted file : {ACCEPTED_FILE}"
    )

    print(
        f"Pending file  : {PENDING_FILE}"
    )

    print(
        f"Rejected file : {REJECTED_FILE}"
    )

    print()
    print(
        "Growth-stage validation complete."
    )


if __name__ == "__main__":
    main()
