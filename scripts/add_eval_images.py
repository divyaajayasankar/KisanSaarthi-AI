"""Add images from a downloaded dataset folder to data/real_field_eval.

    python -m scripts.add_eval_images list <folder>
    python -m scripts.add_eval_images add --crop chilli --src <folder> [--only-class text] [--count 5]
    python -m scripts.add_eval_images fix
    python -m scripts.build_eval_metadata

Copies only readable JPEG/PNG/WEBP images, skips images already in the evaluation set,
spreads the pick across sub-folders, and logs every source path to reports/eval_added_log.csv.
The folder name is only a hint of the disease, never written as a label. --src is never changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import shutil
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.services.image_quality_service import ImageValidationError, validate_image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "data" / "real_field_eval"
METADATA = EVAL_DIR / "metadata.csv"
INVALID_DIR = EVAL_DIR / "_invalid"
REPORTS = PROJECT_ROOT / "reports"
LOG = REPORTS / "eval_added_log.csv"

CROPS = [
    "rice", "wheat", "maize", "tomato", "chilli", "brinjal", "onion", "potato",
    "okra", "cabbage", "groundnut", "chickpea", "mustard", "cotton", "banana",
]
TARGET = 5
SUFFIX_TYPE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
GENERIC_FOLDERS = {
    "train", "test", "val", "valid", "validation", "images", "image", "img", "data", "dataset",
    "orig", "original", "originals", "raw", "augmented", "aug", "jpg", "jpeg", "png",
}
COLUMNS = ["crop", "disease", "filename", "source", "dataset", "license"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


REAL_TYPE = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
TYPE_SUFFIX = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def real_type(path: Path, data: bytes) -> str:
    """MIME type from the image content. Some datasets name JPEG files .png."""
    try:
        with Image.open(BytesIO(data)) as image:
            found = REAL_TYPE.get((image.format or "").upper())
    except (OSError, ValueError):
        found = None
    return found or SUFFIX_TYPE[path.suffix.lower()]


def real_suffix(path: Path) -> str:
    return TYPE_SUFFIX[real_type(path, path.read_bytes())]


def is_valid(path: Path) -> bool:
    try:
        data = path.read_bytes()
        validate_image(filename=path.name, content_type=real_type(path, data), image_bytes=data)
        return True
    except (ImageValidationError, OSError):
        return False


def class_name(path: Path, src: Path) -> str:
    """Nearest parent folder under src that is not a generic name."""
    for parent in path.parents:
        if parent == src.parent:
            break
        if parent.name.lower() not in GENERIC_FOLDERS and parent != src:
            return parent.name
    return src.name


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "class"


def source_images(src: Path) -> list[Path]:
    return [p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIX_TYPE]


def eval_hashes() -> set[str]:
    hashes: set[str] = set()
    for p in EVAL_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUFFIX_TYPE:
            hashes.add(sha256(p))
    return hashes


def valid_in_crop(crop: str) -> list[Path]:
    folder = EVAL_DIR / crop
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUFFIX_TYPE and is_valid(p))


def cmd_list(args: argparse.Namespace) -> None:
    src = Path(args.src).resolve()
    if not src.exists():
        raise SystemExit(f"Folder not found: {src}")
    groups: dict[str, int] = defaultdict(int)
    for path in source_images(src):
        groups[str(path.parent.relative_to(src))] += 1
    if not groups:
        raise SystemExit("No JPEG, PNG or WEBP images found under that folder.")
    print(f"{'images':>7}  folder (relative to {src.name})")
    for folder, count in sorted(groups.items()):
        print(f"{count:>7}  {folder}")
    print(f"\nTotal images: {sum(groups.values())}")


def cmd_add(args: argparse.Namespace) -> None:
    if args.crop not in CROPS:
        raise SystemExit(f"--crop must be one of: {', '.join(CROPS)}")
    src = Path(args.src).resolve()
    if not src.exists():
        raise SystemExit(f"Folder not found: {src}")

    dest = EVAL_DIR / args.crop
    dest.mkdir(parents=True, exist_ok=True)
    have = valid_in_crop(args.crop)
    need = args.count - len(have)
    if need <= 0:
        print(f"{args.crop}: already has {len(have)} valid images. Nothing to add.")
        return

    known = eval_hashes()
    rng = random.Random(args.seed)
    only = args.only_class.lower() if args.only_class else None

    groups: dict[str, list[Path]] = defaultdict(list)
    for path in source_images(src):
        group = class_name(path, src)
        if only and only not in group.lower():
            continue
        groups[group].append(path)
    if not groups:
        raise SystemExit("No matching images under --src.")
    for items in groups.values():
        rng.shuffle(items)
    order = sorted(groups)
    rng.shuffle(order)

    chosen: list[tuple[Path, str]] = []
    skipped_invalid = skipped_dup = 0
    cursor = {g: 0 for g in order}
    while len(chosen) < need and any(cursor[g] < len(groups[g]) for g in order):
        for group in order:
            if len(chosen) >= need:
                break
            while cursor[group] < len(groups[group]):
                path = groups[group][cursor[group]]
                cursor[group] += 1
                if not is_valid(path):
                    skipped_invalid += 1
                    continue
                digest = sha256(path)
                if digest in known:
                    skipped_dup += 1
                    continue
                known.add(digest)
                chosen.append((path, group))
                break

    REPORTS.mkdir(parents=True, exist_ok=True)
    new_log = not LOG.exists()
    counters: dict[str, int] = defaultdict(int)
    with LOG.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if new_log:
            writer.writerow(["crop", "filename", "source_path (under --src)", "src_folder"])
        for path, group in chosen:
            base = f"{args.crop}_{slug(group)}"
            counters[base] += 1
            suffix = real_suffix(path)
            name = f"{base}_{counters[base]:02d}{suffix}"
            while (dest / name).exists():
                counters[base] += 1
                name = f"{base}_{counters[base]:02d}{suffix}"
            shutil.copy2(path, dest / name)
            writer.writerow([args.crop, name, str(path.relative_to(src)), str(src)])
            print(f"  added {args.crop}/{name}   <- {path.relative_to(src)}")

    total = len(have) + len(chosen)
    print(f"\n{args.crop}: {total} valid images (target {args.count}).")
    if skipped_invalid or skipped_dup:
        print(f"Skipped {skipped_invalid} unreadable and {skipped_dup} duplicate files.")
    if total < args.count:
        print(f"Only {total} usable images were found. Use another --src or add your own photos.")


def cmd_fix(_: argparse.Namespace) -> None:
    moved: list[tuple[str, str]] = []
    for crop in CROPS:
        folder = EVAL_DIR / crop
        if not folder.exists():
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in SUFFIX_TYPE and not is_valid(path):
                target_dir = INVALID_DIR / crop
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / path.name
                if target.exists():
                    target = target_dir / f"{path.stem}_{sha256(path)[:8]}{path.suffix}"
                shutil.move(str(path), str(target))
                moved.append((crop, path.name))
                print(f"  moved {crop}/{path.name} -> _invalid/{crop}/{target.name}")

    if METADATA.exists() and moved:
        with METADATA.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        drop = set(moved)
        kept = [r for r in rows if (r.get("crop", "").strip().lower(), r.get("filename", "").strip()) not in drop]
        with METADATA.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(kept)
        print(f"metadata.csv: removed {len(rows) - len(kept)} rows for the moved files.")

    print(f"\n{len(moved)} unreadable image(s) moved to data\\real_field_eval\\_invalid (nothing deleted).")
    if moved:
        print("Next: python -m scripts.add_eval_images add --crop <crop> --src <folder>   to refill to 5.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="show folders and image counts in a download")
    p_list.add_argument("src")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="copy valid images into data/real_field_eval/<crop>")
    p_add.add_argument("--crop", required=True)
    p_add.add_argument("--src", required=True)
    p_add.add_argument("--count", type=int, default=TARGET, help="images wanted for this crop (default 5)")
    p_add.add_argument("--seed", type=int, default=42)
    p_add.add_argument("--only-class", default="", help="only folders whose name contains this text")
    p_add.set_defaults(func=cmd_add)

    p_fix = sub.add_parser("fix", help="move unreadable evaluation images to _invalid and drop their metadata rows")
    p_fix.set_defaults(func=cmd_fix)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
