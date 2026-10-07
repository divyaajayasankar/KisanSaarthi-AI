import ast
import json
import random
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import PurePosixPath, Path

ZIP = Path(sys.argv[1])
OUT = Path(sys.argv[2]).resolve()
CONFIG = Path(sys.argv[3]).resolve()
CAP = int(sys.argv[4]) if len(sys.argv) > 4 else 200

MAP = {
    "banana_bract_mosaic_virus": "bract_mosaic_virus",
    "banana_cordana": "cordana",
    "banana_healthy": "healthy",
    "banana_insectpest": "insect_pest",
    "banana_moko": "moko",
    "banana_panama": "panama_wilt",
    "banana_pestalotiopsis": "pestalotiopsis",
    "banana_sigatoka": "sigatoka",
    "banana_yb_sigatoka": "yellow_sigatoka",
}
EXT = {".jpg", ".jpeg", ".png", ".webp"}

with zipfile.ZipFile(ZIP) as z:
    names_all = set(z.namelist())
    yaml_name = next(n for n in names_all if n.lower().endswith("data.yaml"))
    text = z.read(yaml_name).decode("utf-8", "replace")
    names = [str(n) for n in ast.literal_eval(re.search(r"names\s*:\s*(\[.*?\])", text, re.S).group(1))]
    ids = {i: MAP[n] for i, n in enumerate(names) if n in MAP}
    groups = defaultdict(dict)
    for info in z.infolist():
        p = PurePosixPath(info.filename)
        if info.is_dir() or p.suffix.lower() not in EXT or "/images/" not in info.filename:
            continue
        lab = str(PurePosixPath(re.sub(r"/images/", "/labels/", info.filename, count=1)).with_suffix(".txt"))
        if lab not in names_all:
            continue
        found = {int(s.split()[0]) for s in z.read(lab).decode("utf-8", "replace").splitlines() if s.split() and s.split()[0].isdigit()}
        if len(found) != 1 or next(iter(found)) not in ids:
            continue
        key = p.name.split(".rf.")[0]
        groups[ids[next(iter(found))]].setdefault(key, info)
    rng = random.Random(42)
    total = 0
    for cls in sorted(groups):
        items = list(groups[cls].values())
        rng.shuffle(items)
        folder = OUT / cls
        folder.mkdir(parents=True, exist_ok=True)
        for info in items[:CAP]:
            (folder / PurePosixPath(info.filename).name).write_bytes(z.read(info))
        n = min(len(items), CAP)
        total += n
        print(f"{n:>4} of {len(items):>4} unique photos  {cls}")

cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
cfg["crops"]["banana"] = {
    "source": "Mendeley Data 6243z8r6t6 v1 (Roboflow export, Multi-Crop Disease Dataset)",
    "license": "TO_VERIFY",
    "classes": {cls: [f"banana/{cls}"] for cls in sorted(groups)},
}
CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print(f"\nExtracted {total} images. Config updated for banana ({len(groups)} classes).")
