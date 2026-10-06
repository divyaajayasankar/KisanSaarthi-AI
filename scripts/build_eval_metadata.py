"""Audit data/real_field_eval and keep metadata.csv honest.

    python -m scripts.build_eval_metadata

* Counts images per crop against the target of 5 each (15 crops, 75 images).
* Adds a metadata.csv row for every image that has none. Every field the
  script cannot know (disease, source, dataset, license) is TO_VERIFY.
  Existing rows are never changed.
* Writes reports/metadata_filename_hints.csv: the disease words found in
  file names, for YOU to confirm. They are hints, not labels, and are not
  copied into metadata.csv.
* Flags unreadable images and byte-identical duplicates.

Rows whose disease is TO_VERIFY are excluded from accuracy metrics by
scripts/evaluate_real_field.py.
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from app.services.image_quality_service import ImageValidationError, validate_image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "data" / "real_field_eval"
METADATA = EVAL_DIR / "metadata.csv"
REPORTS = PROJECT_ROOT / "reports"

CROPS = [
    "rice", "wheat", "maize", "tomato", "chilli", "brinjal", "onion", "potato",
    "okra", "cabbage", "groundnut", "chickpea", "mustard", "cotton", "banana",
]
TARGET_PER_CROP = 5
COLUMNS = ["crop", "disease", "filename", "source", "dataset", "license"]
UNKNOWN = "TO_VERIFY"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GENERIC_WORDS = {"disease", "diseased", "affected", "leaf", "image", "img", "sample", "field", "real"}


def list_images(crop: str) -> list[Path]:
    folder = EVAL_DIR / crop
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def filename_hint(crop: str, filename: str) -> str:
    stem = Path(filename).stem.lower()
    stem = re.sub(r"[_\-\s]*\d+$", "", stem)
    stem = re.sub(rf"^{re.escape(crop)}[_\-\s]*", "", stem)
    words = [w for w in re.split(r"[_\-\s]+", stem) if w and w not in GENERIC_WORDS]
    return " ".join(words)


def read_metadata() -> list[dict[str, str]]:
    if not METADATA.exists():
        return []
    with METADATA.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    rows = read_metadata()
    known = {(row.get("crop", "").strip().lower(), row.get("filename", "").strip()) for row in rows}

    added = 0
    hints: list[list[str]] = []
    problems: list[str] = []
    seen_hash: dict[str, str] = {}
    total = 0

    print(f"{'crop':<10} {'images':>6} / {TARGET_PER_CROP}")
    for crop in CROPS:
        images = list_images(crop)
        total += len(images)
        print(f"{crop:<10} {len(images):>6}{'' if len(images) >= TARGET_PER_CROP else '   <- needs ' + str(TARGET_PER_CROP - len(images)) + ' more'}")

        for path in images:
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hash:
                problems.append(f"duplicate image: {crop}/{path.name} == {seen_hash[digest]}")
            seen_hash[digest] = f"{crop}/{path.name}"

            content_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[path.suffix.lower()]
            try:
                validate_image(filename=path.name, content_type=content_type, image_bytes=data)
            except ImageValidationError as exc:
                problems.append(f"invalid image: {crop}/{path.name}: {exc}")

            if (crop, path.name) not in known:
                rows.append({"crop": crop, "disease": UNKNOWN, "filename": path.name,
                             "source": UNKNOWN, "dataset": UNKNOWN, "license": UNKNOWN})
                known.add((crop, path.name))
                added += 1

            hint = filename_hint(crop, path.name)
            if hint:
                hints.append([crop, path.name, hint])

    with METADATA.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with (REPORTS / "metadata_filename_hints.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["crop", "filename", "disease_word_in_filename (confirm before using as a label)"])
        writer.writerows(hints)

    unverified = sum(1 for row in rows if UNKNOWN in (row.get("disease"), row.get("source"), row.get("dataset"), row.get("license")))
    print(f"\nImages: {total} / {TARGET_PER_CROP * len(CROPS)}")
    print(f"metadata.csv rows: {len(rows)} ({added} added this run, {unverified} still have TO_VERIFY fields)")
    print(f"Filename hints written: reports/metadata_filename_hints.csv ({len(hints)})")
    for problem in problems:
        print("PROBLEM:", problem)
    if total < TARGET_PER_CROP * len(CROPS):
        print("The evaluation set is NOT complete.")


if __name__ == "__main__":
    main()
