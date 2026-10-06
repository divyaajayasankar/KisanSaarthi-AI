import csv
from pathlib import Path

from app.data.cibrc import (
    REQUIRED_COLUMNS,
    validate_registry_row,
)


INPUT = Path("data/cibrc/normalized_registry_multicrop.csv")
ACCEPTED = Path("data/cibrc/accepted_verified.csv")
PENDING = Path("data/cibrc/pending_verification.csv")
REJECTED = Path("data/cibrc/rejected.csv")


if not INPUT.exists():
    raise FileNotFoundError(
        f"Missing file: {INPUT}"
    )


with INPUT.open(
    "r",
    newline="",
    encoding="utf-8-sig",
) as file:

    reader = csv.DictReader(file)

    missing_columns = (
        set(REQUIRED_COLUMNS)
        - set(reader.fieldnames or [])
    )

    if missing_columns:
        raise ValueError(
            "Missing CSV columns: "
            + ", ".join(sorted(missing_columns))
        )

    accepted_rows = []
    pending_rows = []
    rejected_rows = []

    for row_number, row in enumerate(
        reader,
        start=2,
    ):

        status, cleaned, reason = (
            validate_registry_row(row)
        )

        cleaned["validation_reason"] = reason
        cleaned["source_csv_row"] = row_number

        if status == "accepted":
            accepted_rows.append(cleaned)

        elif status == "pending":
            pending_rows.append(cleaned)

        else:
            rejected_rows.append(cleaned)


OUTPUT_FIELDS = (
    REQUIRED_COLUMNS
    + [
        "validation_reason",
        "source_csv_row",
    ]
)


def write_csv(path, rows):

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_FIELDS,
        )

        writer.writeheader()
        writer.writerows(rows)


write_csv(
    ACCEPTED,
    accepted_rows,
)

write_csv(
    PENDING,
    pending_rows,
)

write_csv(
    REJECTED,
    rejected_rows,
)


print(f"Accepted verified : {len(accepted_rows)}")
print(f"Pending verify    : {len(pending_rows)}")
print(f"Rejected          : {len(rejected_rows)}")

print()
print(f"Accepted file: {ACCEPTED}")
print(f"Pending file : {PENDING}")
print(f"Rejected file: {REJECTED}")
