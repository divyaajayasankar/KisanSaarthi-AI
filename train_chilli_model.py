"""Train and register the chilli photo model from the local 'cropped' dataset.

Run from the project folder:
    .\\.venv\\Scripts\\python.exe train_chilli_model.py

Reads data/source_datasets/cropped/cropped/<class folders>, fills the chilli
entry in data/vision/crop_datasets.json, adds the alias 'murda complex' ->
'Thrips' so that class reaches the registry row for Thrips; Mites, then runs
scripts/train_crop_model.py. The model is marked validated only if held-out
macro-F1 reaches 0.80. Images identical to anything in data/real_field_eval
are excluded automatically.

The dataset source and licence stay TO_VERIFY; training records that in the
model card. Confirm where the folder came from before you describe it.
Extra arguments are passed to the trainer, for example --epochs 12.
"""
import json
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
if not (root / "app" / "main.py").exists():
    sys.exit("Run this from the project folder (the one that contains app\\main.py).")

BASE = "cropped/cropped"
CLASSES = {
    "cercospora": f"{BASE}/cercospora",
    "healthy": f"{BASE}/healthy",
    "murda_complex": f"{BASE}/murda complex(mites,trips)",
    "nutritional_deficiency": f"{BASE}/nutritional",
    "powdery_mildew": f"{BASE}/powdery mildew",
}
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
source_root = root / "data" / "source_datasets"
counts = {}
for name, rel in CLASSES.items():
    folder = source_root / rel
    if not folder.is_dir():
        sys.exit(f"Missing folder: {folder}")
    counts[name] = sum(1 for p in folder.iterdir() if p.suffix.lower() in SUFFIXES)
print("Images per class:", counts)
if min(counts.values()) < 20:
    sys.exit("A class has fewer than 20 images. Stopping.")

cfg_path = root / "data" / "vision" / "crop_datasets.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
entry = cfg["crops"].setdefault("chilli", {"source": "TO_VERIFY", "license": "TO_VERIFY"})
entry["classes"] = {name: [rel] for name, rel in CLASSES.items()}
cfg_path.write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("Updated", cfg_path.relative_to(root))

alias_path = root / "data" / "registry" / "pest_aliases.csv"
if alias_path.exists():
    raw = alias_path.read_bytes().decode("utf-8")
    if "chilli,murda complex," not in raw:
        nl = "\r\n" if "\r\n" in raw else "\n"
        alias_path.write_bytes((raw.rstrip("\r\n") + nl + "chilli,murda complex,Thrips,en" + nl).encode("utf-8"))
        print("Added alias: chilli, murda complex -> Thrips")

cmd = [sys.executable, "-m", "scripts.train_crop_model", "--crop", "chilli", "--epochs", "8",
       "--min-macro-f1", "0.80", "--accept-unverified-license"] + sys.argv[1:]
print("Running:", " ".join(cmd))
code = subprocess.call(cmd, cwd=str(root))

registry = root / "data" / "models" / "model_registry.json"
if registry.exists():
    model = json.loads(registry.read_text(encoding="utf-8")).get("models", {}).get("chilli")
    if model:
        print("\nchilli validated:", model.get("validated"), "| labels:", model.get("labels"))
        print("validation:", json.dumps(model.get("validation", {}))[:400])
    else:
        print("\nNo chilli entry was written.")
sys.exit(code)
