"""Report which alias-table entries resolve to a verified registry row.

    python -m scripts.validate_pest_aliases

Writes reports/pest_alias_validation.csv. An alias with status
'no_registry_match' is harmless (the advisory engine will abstain with
registration_missing) but shows where registry coverage is missing.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.db import SessionLocal
from app.services.pest_alias_service import load_aliases, match_registry, registered_pests_for_crop


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_ROOT / "reports" / "pest_alias_validation.csv"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    aliases = load_aliases()
    matched = 0

    with SessionLocal() as db, OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["crop", "input_alias", "canonical_pest", "language", "status", "registry_pest"])
        crops_seen: set[str] = set()
        for alias in aliases:
            registry_pest, _ = match_registry(db, alias.crop, alias.canonical)
            status = "matched" if registry_pest else "no_registry_match"
            matched += bool(registry_pest)
            writer.writerow([alias.crop, alias.alias, alias.canonical, alias.language, status, registry_pest or ""])
            crops_seen.add(alias.crop)

        print("Registry pest strings per crop:")
        for crop in sorted(crops_seen):
            pests = registered_pests_for_crop(db, crop)
            print(f"  {crop:<10} {pests if pests else 'NONE'}")

    print(f"\n{matched}/{len(aliases)} aliases resolve to a verified registry row.")
    print(f"Report: {OUTPUT}")


if __name__ == "__main__":
    main()
