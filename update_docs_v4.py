"""Updates README.md and DEPLOYMENT.md for the second photo model (chilli) and the laptop smoke test.

Run from the project folder:
    .\\.venv\\Scripts\\python.exe update_docs_v4.py

Safe to run twice. Edits only the exact sentences listed below; anything it
cannot find is reported and skipped.
"""
import sys
from pathlib import Path

root = Path.cwd()
if not (root / "app" / "main.py").exists():
    sys.exit("Run this from the project folder (the one that contains app\\main.py).")

PAIRS = {
    "README.md": [
        ("- One crop image model is validated (banana, pilot, trained on a public Mendeley\n"
         "  dataset; check its licence before redistribution). Every other crop abstains on\n"
         "  an image until a model is trained and validated for it. Within banana only\n"
         "  Sigatoka and yellow Sigatoka map to a registry row; other banana classes abstain.\n",
         "- Two crop image models are validated: banana (pilot, trained on a public Mendeley\n"
         "  dataset; check its licence before redistribution; held-out macro-F1 0.972) and chilli\n"
         "  (pilot, trained on the local 'cropped' folder, 527 images in 5 classes; held-out\n"
         "  macro-F1 0.889; dataset source and licence still TO_VERIFY). Both scores come from a\n"
         "  split of the training dataset and are not field accuracy. Every other crop abstains on\n"
         "  an image until a model is trained and validated for it. Within banana only\n"
         "  Sigatoka and yellow Sigatoka map to a registry row; other banana classes abstain.\n"
         "  Within chilli, the murda complex class is mapped to the Thrips and Mites registry row by\n"
         "  an alias added in `data/registry/pest_aliases.csv`; that mapping needs expert review.\n"
         "  Chilli classes with no verified registry row return the disease name and no dose.\n"),
        ("  with a validated photo model (banana).\n", "  with a validated photo model (banana, chilli).\n"),
        ("| MobileNetV3 banana model with disease name and affected region |",
         "| MobileNetV3 banana and chilli models with disease name and affected region |"),
    ],
    "DEPLOYMENT.md": [
        ("so the banana model can run;", "so the banana and chilli models can run;"),
        ("- Photo diagnosis and affected region work for one crop (banana). The held-out macro-F1 of 0.9722 comes from one public dataset and is not field accuracy.",
         "- Photo diagnosis and affected region work for two crops (banana, chilli). The held-out macro-F1 scores (banana 0.9722, chilli 0.8893) come from splits of their own training datasets and are not field accuracy. The chilli dataset source and licence are still TO_VERIFY."),
        ("Run against a one-row test database; rerun on your own database before the review",
         "Passed 6 of 6 on the project laptop with the real registry and live weather; also 7 of 7 in the build sandbox"),
    ],
}
for name, pairs in PAIRS.items():
    path = root / name
    if not path.exists():
        print("MISSING   ", name)
        continue
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    work = raw.replace("\r\n", "\n")
    changed = False
    for old, new in pairs:
        if new in work:
            print("already   ", name, "|", new[:50].replace("\n", " "))
        elif old in work:
            work = work.replace(old, new, 1)
            changed = True
            print("patched   ", name, "|", new[:50].replace("\n", " "))
        else:
            print("SKIPPED   ", name, "| not found:", old[:50].replace("\n", " "))
    if changed:
        path.write_bytes((work.replace("\n", "\r\n") if crlf else work).encode("utf-8"))
print("done")
