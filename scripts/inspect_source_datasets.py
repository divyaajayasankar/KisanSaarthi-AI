"""List image folders under data/source_datasets to fill data/vision/crop_datasets.json.

    python -m scripts.inspect_source_datasets
    python -m scripts.inspect_source_datasets --depth 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(PROJECT_ROOT / "data" / "source_datasets"))
    parser.add_argument("--depth", type=int, default=4)
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Not found: {root}")

    print(f"{'direct images':>13}  {'total images':>12}  folder (relative to {root.name})")
    for directory in sorted(path for path in root.rglob("*") if path.is_dir()):
        relative = directory.relative_to(root)
        if len(relative.parts) > args.depth:
            continue
        direct = sum(1 for path in directory.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
        total = sum(1 for path in directory.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
        if total:
            print(f"{direct:>13}  {total:>12}  {relative.as_posix()}")
    print("\nA usable class folder has many direct images of ONE disease (or healthy).")
    print("Avoid pre-augmented copies (rotated/, augmented/) to keep the validation split honest.")


if __name__ == "__main__":
    main()
