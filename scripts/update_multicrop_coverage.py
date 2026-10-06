"""Recompute per-crop capability flags in data/coverage/crop_coverage.json
from the verified rows actually present in the database.

Previously this file was a byte-identical copy of ingest_crop_registry_15.py
and never touched coverage.

Usage:
    python -m scripts.update_multicrop_coverage            # report only
    python -m scripts.update_multicrop_coverage --write    # update flags
    python -m scripts.update_multicrop_coverage --write --recompute-status

Flags derived from the DB:
    registry           verified, non-test RegistryEntry rows exist
    phi                every such row has phi_days or phi_not_applicable
    growth_stage       verified GrowthStageRule rows exist
    treatment_history  verified TreatmentHistoryRule rows exist
    resistance         ResistanceRule rows exist
    soil               CropSoilRule rows exist

"weather" and "rag" are not DB-derived and are left as they are.
"status" is changed only with --recompute-status:
    supported       all DB-derived flags true
    partial_support registry true, some other flag false
    unsupported     registry false
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import func

from app.db import SessionLocal
from app.models import RegistryEntry
from app.models_crop_soil import CropSoilRule
from app.models_growth_stage import GrowthStageRule
from app.models_resistance import ResistanceRule
from app.models_treatment_history import TreatmentHistoryRule


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_FILE = PROJECT_ROOT / "data" / "coverage" / "crop_coverage.json"

DB_FLAGS = (
    "registry",
    "phi",
    "growth_stage",
    "treatment_history",
    "resistance",
    "soil",
)


def _has_rows(db, model, crop: str, verified_only: bool = False) -> bool:
    query = db.query(model).filter(func.lower(model.crop) == crop.lower())
    if verified_only and hasattr(model, "verified"):
        query = query.filter(model.verified.is_(True))
    if hasattr(model, "is_test_data"):
        query = query.filter(model.is_test_data.is_(False))
    return query.first() is not None


def compute_flags(db, crop: str) -> dict[str, bool]:
    registry_rows = (
        db.query(RegistryEntry)
        .filter(func.lower(RegistryEntry.crop) == crop.lower())
        .filter(RegistryEntry.verified.is_(True))
        .filter(RegistryEntry.is_test_data.is_(False))
        .all()
    )

    registry = bool(registry_rows)
    phi = registry and all(
        row.phi_not_applicable or row.phi_days is not None
        for row in registry_rows
    )

    return {
        "registry": registry,
        "phi": phi,
        "growth_stage": _has_rows(db, GrowthStageRule, crop, verified_only=True),
        "treatment_history": _has_rows(db, TreatmentHistoryRule, crop, verified_only=True),
        "resistance": _has_rows(db, ResistanceRule, crop),
        "soil": _has_rows(db, CropSoilRule, crop),
    }


def derive_status(flags: dict[str, bool]) -> str:
    if not flags["registry"]:
        return "unsupported"
    if all(flags[name] for name in DB_FLAGS):
        return "supported"
    return "partial_support"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--recompute-status", action="store_true")
    args = parser.parse_args()

    records = json.loads(COVERAGE_FILE.read_text(encoding="utf-8"))
    changes = 0

    with SessionLocal() as db:
        for record in records:
            crop = record["crop"]
            flags = compute_flags(db, crop)

            for name, value in flags.items():
                if record.get(name) != value:
                    print(f"{crop:<10} {name:<18} {record.get(name)} -> {value}")
                    changes += 1
                    if args.write:
                        record[name] = value

            if args.recompute_status:
                status = derive_status(flags)
                if record.get("status") != status:
                    print(f"{crop:<10} {'status':<18} {record.get('status')} -> {status}")
                    changes += 1
                    if args.write:
                        record["status"] = status

    if args.write and changes:
        COVERAGE_FILE.write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {changes} change(s) to {COVERAGE_FILE}")
    else:
        print(f"{changes} difference(s) found. {'No write needed.' if not changes else 'Run with --write to apply.'}")


if __name__ == "__main__":
    main()
