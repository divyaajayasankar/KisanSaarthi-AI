"""Context-sensitivity evaluation of the deterministic safety layer.

    python -m scripts.evaluate_personalization

Takes the verified registry rows that are actually in the configured
database and changes ONE farmer-context dimension at a time. For each
case the expected outcome is computed independently from the stored rule
(not by calling the code under test) and compared with the engine.

Dimensions:
    dose            same product, different field area / unit
    phi             harvest 1 day inside vs exactly at the registered PHI
    growth_stage    each stage vs the stored allowed_stages of the rule
    history         previous applications vs the stored maximum / interval
    weather         SYNTHETIC forecasts (clearly labeled) vs documented thresholds

This checks that advice changes when, and only when, the context says it
should. It does not measure agronomic effectiveness and it is not a
comparison with a generic LLM (that needs an LLM key and is not run here).
With an empty registry the script says so and produces no results.

Output: reports/personalization_eval.csv and reports/personalization_eval.md
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import func

from app.db import SessionLocal
from app.models import RegistryEntry
from app.models_growth_stage import GrowthStageRule
from app.models_treatment_history import TreatmentHistoryRule
from app.services.constraint_engine import evaluate_advisory
from app.services.growth_stage_service import evaluate_farmer_growth_stage
from app.services.treatment_history_service import evaluate_treatment_history
from app.services.weather_rules import evaluate_weather_safety


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS = PROJECT_ROOT / "reports"

# Independent literals (hectares per unit), deliberately not imported from the engine.
HECTARES = {"hectare": 1.0, "acre": 0.40468564224, "cent": 0.0040468564224, "guntha": 0.010117141056}
AREAS = [(0.5, "acre"), (1, "acre"), (2.5, "acre"), (0.5, "hectare"), (2, "hectare"), (10, "cent"), (20, "guntha")]
STAGES = ["seedling", "vegetative", "flowering", "fruiting", "pre_harvest"]
# Documented rule in app/services/growth_stage_rules.py, restated here on purpose:
# flowering and fruiting are reproductive stages. Other stages map to themselves.
STAGE_GROUP = {"flowering": "reproductive", "fruiting": "reproductive"}

SYNTHETIC_WEATHER = [
    ("calm dry day", {"rain_total_mm": 0.0, "max_rain_probability": 0.10, "max_wind_speed_m_s": 1.5}, "proceed"),
    ("rain likely and heavy (0.90, 12 mm)", {"rain_total_mm": 12.0, "max_rain_probability": 0.90, "max_wind_speed_m_s": 1.0}, "delay"),
    ("strong wind (8 m/s)", {"rain_total_mm": 0.0, "max_rain_probability": 0.10, "max_wind_speed_m_s": 8.0}, "delay"),
    ("rain chance 0.30 only", {"rain_total_mm": 0.2, "max_rain_probability": 0.30, "max_wind_speed_m_s": 1.0}, "proceed"),
]


def entry_view(row: RegistryEntry) -> SimpleNamespace:
    return SimpleNamespace(
        crop=row.crop, pest=row.pest, active_ingredient=row.active_ingredient,
        dose_min_per_hectare=row.dose_min_per_hectare, dose_max_per_hectare=row.dose_max_per_hectare,
        dose_unit=row.dose_unit, phi_days=row.phi_days, phi_not_applicable=bool(row.phi_not_applicable),
        verified=row.verified, is_test_data=row.is_test_data,
    )


def case(dimension, crop, pest, scenario, expected, actual, note="") -> dict:
    return {"dimension": dimension, "crop": crop, "pest": pest, "scenario": scenario,
            "expected": expected, "actual": actual, "pass": expected == actual, "note": note}


def dose_cases(row: RegistryEntry) -> list[dict]:
    out = []
    entry = entry_view(row)
    for area, unit in AREAS:
        result = evaluate_advisory(registry_entry=entry, field_area=area, area_unit=unit, expected_harvest_days=1000)
        expected = round(row.dose_min_per_hectare * area * HECTARES[unit], 2)
        actual = result.scaled_dose_min if result.status == "recommend" else result.status
        out.append(case("dose", row.crop, row.pest, f"{area} {unit}", expected, actual, f"{row.dose_min_per_hectare} {row.dose_unit}/ha"))
    return out


def phi_cases(row: RegistryEntry) -> list[dict]:
    entry = entry_view(row)
    if row.phi_not_applicable:
        result = evaluate_advisory(registry_entry=entry, field_area=1, area_unit="acre", expected_harvest_days=0)
        return [case("phi", row.crop, row.pest, "PHI not applicable, harvest in 0 days", "recommend", result.status)]
    if not row.phi_days or row.phi_days < 1:
        return []
    inside = evaluate_advisory(registry_entry=entry, field_area=1, area_unit="acre", expected_harvest_days=row.phi_days - 1)
    at = evaluate_advisory(registry_entry=entry, field_area=1, area_unit="acre", expected_harvest_days=row.phi_days)
    return [
        case("phi", row.crop, row.pest, f"harvest in {row.phi_days - 1} d, PHI {row.phi_days} d", "abstain", inside.status),
        case("phi", row.crop, row.pest, f"harvest in {row.phi_days} d, PHI {row.phi_days} d", "recommend", at.status),
    ]


def growth_cases(db, row: RegistryEntry) -> list[dict]:
    rule = (
        db.query(GrowthStageRule)
        .filter(func.lower(GrowthStageRule.crop) == row.crop.lower())
        .filter(func.lower(GrowthStageRule.pest) == row.pest.lower())
        .filter(func.lower(GrowthStageRule.active_ingredient) == row.active_ingredient.lower())
        .filter(GrowthStageRule.verified.is_(True))
        .first()
    )
    if rule is None:
        return []
    allowed = {s.strip().lower().replace(" ", "_") for s in rule.allowed_stages.split(";") if s.strip()}
    out = []
    for stage in STAGES:
        result = evaluate_farmer_growth_stage(db, row.crop, row.pest, row.active_ingredient, stage)
        expected = "pass" if STAGE_GROUP.get(stage, stage) in allowed else "abstain"
        out.append(case("growth_stage", row.crop, row.pest, stage, expected, result["status"], f"allowed: {sorted(allowed)}"))
    return out


def history_cases(db, row: RegistryEntry) -> list[dict]:
    rule = (
        db.query(TreatmentHistoryRule)
        .filter(func.lower(TreatmentHistoryRule.crop) == row.crop.lower())
        .filter(func.lower(TreatmentHistoryRule.pest) == row.pest.lower())
        .filter(func.lower(TreatmentHistoryRule.active_ingredient) == row.active_ingredient.lower())
        .filter(TreatmentHistoryRule.verified.is_(True))
        .first()
    )
    if rule is None or rule.max_applications is None:
        return []
    top = rule.max_applications
    gap = rule.min_interval_days
    below = top - 1
    # A stored repeat interval applies once there is at least one previous
    # application, so the "under the maximum" case must also say how many days
    # have passed. Give exactly the stored interval: only the count is under test.
    days = gap if (gap is not None and below > 0) else None
    suffix = f", {days:g} d since last" if days is not None else ""
    ai = row.active_ingredient
    out = []
    result = evaluate_treatment_history(db, row.crop, row.pest, ai, below, days)
    out.append(case("history", row.crop, row.pest, f"{below} previous (max {top}){suffix}", "pass", result["status"]))
    result = evaluate_treatment_history(db, row.crop, row.pest, ai, top, None)
    out.append(case("history", row.crop, row.pest, f"{top} previous (max {top})", "abstain", result["status"]))
    if gap is not None and below > 0:
        result = evaluate_treatment_history(db, row.crop, row.pest, ai, below, None)
        out.append(case("history", row.crop, row.pest, f"{below} previous, days since last not given (interval {gap:g} d)", "abstain", result["status"]))
        if gap > 0:
            result = evaluate_treatment_history(db, row.crop, row.pest, ai, below, gap - 1)
            out.append(case("history", row.crop, row.pest, f"{below} previous, {gap - 1:g} d since last (interval {gap:g} d)", "abstain", result["status"]))
    return out


def weather_cases() -> list[dict]:
    out = []
    for label, weather, expected in SYNTHETIC_WEATHER:
        out.append(case("weather", "(synthetic)", "", label, expected, evaluate_weather_safety(weather).status,
                        "synthetic forecast, not observed weather"))
    return out


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    results: list[dict] = weather_cases()

    with SessionLocal() as db:
        rows = (
            db.query(RegistryEntry)
            .filter(RegistryEntry.verified.is_(True))
            .filter(RegistryEntry.is_test_data.is_(False))
            .order_by(RegistryEntry.crop, RegistryEntry.id)
            .all()
        )
        if not rows:
            print("The verified registry is empty: dose, PHI, growth-stage and history checks were NOT run.")
            print("Import your data first (scripts/import_local_assets.ps1). Only the synthetic weather checks ran.")

        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (row.crop.lower(), row.pest.lower())
            if key in seen:
                continue
            seen.add(key)
            results += dose_cases(row) + phi_cases(row) + growth_cases(db, row) + history_cases(db, row)

    columns = ["dimension", "crop", "pest", "scenario", "expected", "actual", "pass", "note"]
    with (REPORTS / "personalization_eval.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

    lines = ["# Personalization (context sensitivity) evaluation", "", "| dimension | cases | passed |", "|---|---|---|"]
    for dimension in ("dose", "phi", "growth_stage", "history", "weather"):
        subset = [r for r in results if r["dimension"] == dimension]
        lines.append(f"| {dimension} | {len(subset)} | {sum(r['pass'] for r in subset)} |")
    failed = [r for r in results if not r["pass"]]
    lines += ["", f"Total: {len(results)} cases, {len(results) - len(failed)} passed, {len(failed)} failed.", ""]
    for r in failed:
        lines.append(f"- FAIL {r['dimension']} {r['crop']} / {r['pest']} / {r['scenario']}: expected {r['expected']}, got {r['actual']}")
    (REPORTS / "personalization_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
