"""Sample images of one crop from a YOLO-format dataset ZIP (Roboflow export).

Images sit in <split>/images, labels in <split>/labels/<same name>.txt, and
data.yaml lists the class names ("banana_sigatoka", "groundnut_rust", ...).
The class of an image comes from its label file, never from its file name.

    python -m scripts.yolo_zip_sample list    "<zip>"
    python -m scripts.yolo_zip_sample extract "<zip>" data\\source_datasets\\banana --prefix banana --per-class 3

--prefix   crop name at the start of the class names in data.yaml
--split    test (default), valid or train
Only images whose label file lists classes of that crop and nothing else are used.
Output folders are named after the dataset class, e.g. banana_sigatoka/.
"""

from __future__ import annotations

import argparse
import ast
import random
import re
import zipfile
from collections import defaultdict
from pathlib import PurePosixPath
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def read_names(archive: zipfile.ZipFile) -> list[str]:
    yamls = [n for n in archive.namelist() if n.lower().endswith("data.yaml")]
    if not yamls:
        raise SystemExit("data.yaml not found in the ZIP.")
    text = archive.read(yamls[0]).decode("utf-8", "replace")
    match = re.search(r"names\s*:\s*(\[.*?\])", text, re.DOTALL)
    if not match:
        raise SystemExit("Could not read the names list from data.yaml.")
    return [str(n) for n in ast.literal_eval(match.group(1))]


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "class"


def label_ids(archive: zipfile.ZipFile, image_name: str, known: set[str]) -> set[int] | None:
    label_name = re.sub(r"/images/", "/labels/", image_name, count=1)
    label_name = str(PurePosixPath(label_name).with_suffix(".txt"))
    if label_name not in known:
        return None
    ids: set[int] = set()
    for line in archive.read(label_name).decode("utf-8", "replace").splitlines():
        parts = line.split()
        if parts and parts[0].isdigit():
            ids.add(int(parts[0]))
    return ids


def cmd_list(args: argparse.Namespace) -> None:
    with zipfile.ZipFile(args.zip) as archive:
        names = read_names(archive)
    for index, name in enumerate(names):
        print(f"{index:>3}  {name}")


def cmd_extract(args: argparse.Namespace) -> None:
    out = Path(args.out_dir).resolve()
    rng = random.Random(args.seed)
    limit = int(args.max_mb * 1024 * 1024)
    with zipfile.ZipFile(args.zip) as archive:
        names = read_names(archive)
        wanted = {i for i, n in enumerate(names) if n.lower().startswith(args.prefix.lower() + "_")}
        if not wanted:
            raise SystemExit(f"No class in data.yaml starts with {args.prefix + '_'!r}.")
        known = set(archive.namelist())
        groups: dict[int, list[zipfile.ZipInfo]] = defaultdict(list)
        marker = f"/{args.split}/images/"
        for info in archive.infolist():
            if info.is_dir() or marker not in info.filename or PurePosixPath(info.filename).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if info.file_size > limit:
                continue
            ids = label_ids(archive, info.filename, known)
            if ids and ids <= wanted:
                groups[min(ids)].append(info)
        if not groups:
            raise SystemExit("No images matched. Try --split valid or --split train.")
        total = 0
        for class_id in sorted(groups):
            items = groups[class_id]
            rng.shuffle(items)
            folder = out / slug(names[class_id])
            folder.mkdir(parents=True, exist_ok=True)
            for info in items[: args.per_class]:
                target = folder / PurePosixPath(info.filename).name
                target.write_bytes(archive.read(info))
                total += 1
            print(f"{min(len(items), args.per_class):>4} of {len(items):>5}  {names[class_id]}")
    print(f"\nExtracted {total} images to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("zip")
    p_list.set_defaults(func=cmd_list)
    p_ext = sub.add_parser("extract")
    p_ext.add_argument("zip")
    p_ext.add_argument("out_dir")
    p_ext.add_argument("--prefix", required=True)
    p_ext.add_argument("--split", default="test")
    p_ext.add_argument("--per-class", type=int, default=3)
    p_ext.add_argument("--seed", type=int, default=42)
    p_ext.add_argument("--max-mb", type=float, default=15.0)
    p_ext.set_defaults(func=cmd_extract)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
