"""Unpack a Hugging Face image-classification parquet file into class folders.

    python -m scripts.parquet_to_images <file.parquet> <out_dir> --labels "a,b,c,d"

Needs: pip install pyarrow
Writes <out_dir>/<label name>/<n>.<ext> (image bytes are copied unchanged).
"""

from __future__ import annotations

import argparse
import re
from io import BytesIO
from pathlib import Path

from PIL import Image


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "class"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("parquet")
    parser.add_argument("out_dir")
    parser.add_argument("--labels", default="", help="comma-separated class names in label-id order")
    args = parser.parse_args()

    import pyarrow.parquet as pq

    names = [n.strip() for n in args.labels.split(",") if n.strip()]
    table = pq.read_table(args.parquet).to_pylist()
    out = Path(args.out_dir)
    counts: dict[str, int] = {}
    for row in table:
        image, label = row["image"], row.get("label")
        data = image["bytes"] if isinstance(image, dict) else image
        name = names[label] if names and isinstance(label, int) and label < len(names) else f"label_{label}"
        with Image.open(BytesIO(data)) as probe:
            ext = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(probe.format or "", ".png")
        folder = out / slug(name)
        folder.mkdir(parents=True, exist_ok=True)
        counts[name] = counts.get(name, 0) + 1
        (folder / f"{counts[name]:04d}{ext}").write_bytes(data)
    for name, n in counts.items():
        print(f"{n:6d}  {name}")
    print(f"Total {sum(counts.values())} images -> {out}")


if __name__ == "__main__":
    main()
