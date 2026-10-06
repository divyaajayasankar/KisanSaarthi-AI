import csv
from pathlib import Path

from app.data.cibrc import REQUIRED_COLUMNS


OUTPUT = Path(
    "data/cibrc/normalized_registry_v2.csv"
)

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)


with OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=REQUIRED_COLUMNS,
    )

    writer.writeheader()


print(
    f"Created Phase-2B template: {OUTPUT}"
)
