"""List a dataset ZIP and extract a small sample of images from it.

Use this for large ZIPs (several GB). Nothing is fully extracted.

    # 1. folders and image counts inside the ZIP (reads the index only)
    python -m scripts.zip_sample list "C:\\Users\\you\\Downloads\\Dataset.zip"

    # 2. extract up to 6 images per class folder into a new folder
    python -m scripts.zip_sample extract "C:\\Users\\you\\Downloads\\Dataset.zip" data\\source_datasets\\okra --per-class 6

    # optional: only class folders whose path contains this text
    ... --only banana

    # ZIP inside a ZIP: name the inner ZIP (text match). Nothing is written to disk
    # except the sampled images.
    python -m scripts.zip_sample list "<outer>.zip" --inner Cotton_Original
    python -m scripts.zip_sample extract "<outer>.zip" data\\source_datasets\\cotton --inner Cotton_Original

Images under folders named augmented/augmentation/aug are skipped unless
--include-augmented is given. Images above --max-mb are skipped. The ZIP is
never modified. Output is meant for: python -m scripts.add_eval_images add ...
"""

from __future__ import annotations

import argparse
import contextlib
import random
import re
import zipfile
from collections import defaultdict
from pathlib import PurePosixPath
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
AUG_PATTERN = re.compile(r"(^|[^a-z])aug(ment\w*)?([^a-z]|$)", re.IGNORECASE)
BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


def parts_of(name: str) -> list[str]:
    parts = [p for p in PurePosixPath(name.replace("\\", "/")).parts if p not in ("", "/", ".")]
    return parts


def safe(part: str) -> str:
    return BAD_CHARS.sub("_", part).strip(" .") or "x"


def is_augmented(parts: list[str]) -> bool:
    return any(AUG_PATTERN.search(p) for p in parts[:-1])


def scan(archive: zipfile.ZipFile) -> tuple[dict[str, list[zipfile.ZipInfo]], list[str]]:
    groups: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    other: list[str] = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = parts_of(info.filename)
        if not parts or ".." in parts or parts[0].startswith("__MACOSX"):
            continue
        suffix = Path(parts[-1]).suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            groups["/".join(parts[:-1]) or "(root)"].append(info)
        elif suffix in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            other.append(info.filename)
    return groups, other


@contextlib.contextmanager
def open_archive(path: str, inner: str):
    """Open the ZIP, or ZIPs nested inside it (matched by text). Separate levels with '>'."""
    levels = [p.strip() for p in inner.split(">") if p.strip()]
    with contextlib.ExitStack() as stack:
        archive = stack.enter_context(zipfile.ZipFile(path))
        for text in levels:
            matches = [i for i in archive.infolist() if not i.is_dir() and text.lower() in i.filename.lower() and i.filename.lower().endswith(".zip")]
            if len(matches) != 1:
                names = [i.filename for i in archive.infolist() if i.filename.lower().endswith(".zip")]
                raise SystemExit(f"--inner {text!r} must match exactly one ZIP inside. Found {len(matches)}. ZIPs inside: {names}")
            handle = stack.enter_context(archive.open(matches[0]))
            archive = stack.enter_context(zipfile.ZipFile(handle))
        yield archive


def cmd_list(args: argparse.Namespace) -> None:
    with open_archive(args.zip, args.inner) as archive:
        groups, nested = scan(archive)
    if not groups:
        if nested:
            raise SystemExit(f"No images at this level. ZIPs inside: {nested}. Rerun with --inner <part of a name>.")
        raise SystemExit("No JPEG, PNG or WEBP images in this ZIP.")
    print(f"{'images':>7}  {'aug':>3}  folder")
    for folder, items in sorted(groups.items()):
        aug = "yes" if is_augmented(parts_of(folder + "/x")) else ""
        print(f"{len(items):>7}  {aug:>3}  {folder}")
    print(f"\nTotal images: {sum(len(v) for v in groups.values())}")
    if nested:
        print(f"Nested archives inside the ZIP ({len(nested)}): {nested[:5]}")


def cmd_extract(args: argparse.Namespace) -> None:
    out = Path(args.out_dir).resolve()
    rng = random.Random(args.seed)
    only = args.only.lower()
    limit = int(args.max_mb * 1024 * 1024)
    written = 0
    with open_archive(args.zip, args.inner) as archive:
        groups, nested = scan(archive)
        for folder in sorted(groups):
            parts = parts_of(folder + "/x")
            if only and only not in folder.lower():
                continue
            if is_augmented(parts) and not args.include_augmented:
                continue
            items = [i for i in groups[folder] if i.file_size <= limit]
            rng.shuffle(items)
            keep_parts = [safe(p) for p in parts[:-1]][-2:]
            target_dir = out.joinpath(*keep_parts) if keep_parts else out
            target_dir.mkdir(parents=True, exist_ok=True)
            count = 0
            for info in items[: args.per_class]:
                base = safe(parts_of(info.filename)[-1])
                target = target_dir / base
                if target.exists():
                    target = target_dir / f"{target.stem}_{info.CRC:08x}{target.suffix}"
                with archive.open(info) as src, target.open("wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                count += 1
            written += count
            print(f"{count:>4}  {'/'.join(keep_parts) or '(root)'}")
    print(f"\nExtracted {written} images to {out}")
    if nested:
        print(f"Note: the ZIP contains nested archives {nested[:5]}. Extract those separately.")
    if written == 0:
        print("Nothing matched. Run the list command and check --only.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("zip")
    p_list.add_argument("--inner", default="", help="text matching one ZIP inside the ZIP")
    p_list.set_defaults(func=cmd_list)
    p_ext = sub.add_parser("extract")
    p_ext.add_argument("zip")
    p_ext.add_argument("out_dir")
    p_ext.add_argument("--inner", default="", help="text matching one ZIP inside the ZIP")
    p_ext.add_argument("--per-class", type=int, default=6)
    p_ext.add_argument("--only", default="")
    p_ext.add_argument("--seed", type=int, default=42)
    p_ext.add_argument("--max-mb", type=float, default=15.0)
    p_ext.add_argument("--include-augmented", action="store_true")
    p_ext.set_defaults(func=cmd_extract)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
