"""Fill known provenance in data/real_field_eval/metadata.csv. Never overwrites a real value.

    python -m scripts.fill_eval_provenance

For each image listed in reports/eval_added_log.csv it fills, only where the
cell is still TO_VERIFY:
  disease   the dataset's own class folder name (the label the dataset authors
            gave the image). It is not an annotation made by this project.
  dataset   name of the download, from the table below
  source    page of the download, from the table below
  license   only where it was read from the dataset page; otherwise TO_VERIFY

Images that are not in the log (your older rice, wheat, maize, tomato, chilli
files) stay TO_VERIFY. Fill them from their real source by hand.
A backup is written to metadata.csv.bak.
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path, PureWindowsPath

from scripts.add_eval_images import GENERIC_FOLDERS

ROOT = Path(__file__).resolve().parent.parent
METADATA = ROOT / "data" / "real_field_eval" / "metadata.csv"
LOG = ROOT / "reports" / "eval_added_log.csv"
COLUMNS = ["crop", "disease", "filename", "source", "dataset", "license"]
UNKNOWN = "TO_VERIFY"

# crop -> (dataset, source page, license). License is filled only where it was read on the page.
DATASETS = {
    "okra": ("Okra DiseaseNet Dataset", "https://data.mendeley.com/datasets/nh7zk4hv8z", UNKNOWN),
    "brinjal": ("Mendeley Data pwvpb658rm (real-field eggplant leaf disease)", "https://data.mendeley.com/datasets/pwvpb658rm", UNKNOWN),
    "cabbage": ("Image dataset of Cabbage Crop diseases", "https://data.mendeley.com/datasets/sjmgzhwrxv/1", UNKNOWN),
    "cotton": ("Cotton Leaf Image Dataset for Disease Classification", "https://data.mendeley.com/datasets/t9hgvk2h9p/1", UNKNOWN),
    "banana": ("Multi-Crop Disease Dataset (Roboflow export, 640x640 stretched)", "https://data.mendeley.com/datasets/6243z8r6t6/1", UNKNOWN),
    "groundnut": ("Multi-Crop Disease Dataset (Roboflow export, 640x640 stretched)", "https://data.mendeley.com/datasets/6243z8r6t6/1", UNKNOWN),
    "onion": ("COLD Onion Leaf Disease Classification Dataset", "https://huggingface.co/datasets/Project-AgML/COLD_onion_leaf_disease_classification", "CC-BY-4.0"),
    "potato": ("Potato Leaf Disease Dataset", "https://data.mendeley.com/datasets/d5b3fzpw3g/1", UNKNOWN),
}


def disease_from(source_path: str) -> str:
    parent = PureWindowsPath(source_path.replace("/", "\\")).parent.name
    if not parent or parent.lower() in GENERIC_FOLDERS:
        return UNKNOWN
    text = re.sub(r"^class\s*\d+\s*-\s*", "", parent, flags=re.IGNORECASE)
    return re.sub(r"[_\s]+", " ", text).strip() or UNKNOWN


def main() -> None:
    if not METADATA.exists() or not LOG.exists():
        raise SystemExit("Run build_eval_metadata first and make sure reports/eval_added_log.csv exists.")
    with LOG.open("r", encoding="utf-8-sig", newline="") as handle:
        logged = {(r["crop"].strip().lower(), r["filename"].strip()): r[next(k for k in r if k.startswith("source_path"))] for r in csv.DictReader(handle)}
    with METADATA.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    shutil.copy2(METADATA, METADATA.with_suffix(".csv.bak"))

    filled = 0
    for row in rows:
        key = (row["crop"].strip().lower(), row["filename"].strip())
        if key not in logged:
            continue
        before = dict(row)
        if row.get("disease", UNKNOWN) in ("", UNKNOWN):
            row["disease"] = disease_from(logged[key])
        info = DATASETS.get(key[0])
        if info:
            for column, value in zip(("dataset", "source", "license"), info):
                if row.get(column, UNKNOWN) in ("", UNKNOWN):
                    row[column] = value
        filled += row != before

    with METADATA.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    open_cells = {}
    for row in rows:
        missing = [c for c in COLUMNS if row.get(c, UNKNOWN) in ("", UNKNOWN)]
        if missing:
            open_cells.setdefault(row["crop"], set()).update(missing)
    print(f"Updated {filled} of {len(rows)} rows.")
    for crop, cols in sorted(open_cells.items()):
        print(f"  still TO_VERIFY  {crop:10s} {', '.join(sorted(cols))}")


if __name__ == "__main__":
    main()
