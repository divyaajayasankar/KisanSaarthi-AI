"""Research evaluation suite for KisanSaarthi AI.

    python -m scripts.evaluate_research

Runs on a COPY of the configured database, so nothing is written to the
live database. Outputs reports/research_eval.md, .csv and .json.

What is measured, and against what:

  1  Context-conditional correctness   advisory vs an independent oracle that restates
                                       the stored rules (dose, PHI, stage, history, weather)
  2  Safety compliance rate            share of unsafe scenarios where NO dose is issued
  3  Abstention precision and recall   abstain / delay vs the oracle
  4  Dose accuracy                     scaled dose vs independently computed dose
  5  Waiting-period compliance        scenarios inside the PHI never get a dose
  6  Tool-argument accuracy            gold utterances (en, hi, ta, te) vs extracted fields
  7  Irrelevant-context stability      distractor turns must not change the answer
  8  Multilingual consistency          same case in four languages, same decision and dose
  9  Retrieval hit@k                   keyword retrieval over the verified evidence file
 10  Evidence grounding                every issued product and dose traces to a registry row
 11  Latency                           engine and chat turn
 12  Baselines                         B1 direct LLM (needs a key), B2 and B3 SIMULATED
 13  Ablations                         one context source removed at a time

Weather is a FIXED synthetic forecast in every scenario (labelled as such).
Live weather is not used, so results do not depend on the day.
Baselines B2 and B3 are rule-based stand-ins written for this script. They
are not real systems. B1 is NOT RUN unless an LLM key is configured.
Nothing here measures agronomic effectiveness.
"""

from __future__ import annotations

import csv
import itertools
import json
import shutil
import statistics
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import RegistryEntry
from app.models_growth_stage import GrowthStageRule
from app.models_treatment_history import TreatmentHistoryRule
from app.schemas import AdvisoryRequest
from app.services.weather_service import WeatherServiceError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS = PROJECT_ROOT / "reports"

# Independent literals, deliberately not imported from the engine.
HECTARES = {"hectare": 1.0, "acre": 0.40468564224, "cent": 0.0040468564224, "guntha": 0.010117141056}
STAGE_GROUP = {"flowering": "reproductive", "fruiting": "reproductive"}
WIND_LIMIT = 3.0
RAIN_PROB_LIMIT = 0.60
RAIN_MM_LIMIT = 1.0

WEATHER = {
    "safe": {"rain_total_mm": 0.0, "max_rain_probability": 0.10, "max_wind_speed_m_s": 1.5,
             "min_temperature_c": 22, "max_temperature_c": 31, "city": "Synthetic"},
    "rain": {"rain_total_mm": 12.0, "max_rain_probability": 0.90, "max_wind_speed_m_s": 1.0,
             "min_temperature_c": 22, "max_temperature_c": 28, "city": "Synthetic"},
    "wind": {"rain_total_mm": 0.0, "max_rain_probability": 0.10, "max_wind_speed_m_s": 8.0,
             "min_temperature_c": 22, "max_temperature_c": 31, "city": "Synthetic"},
    "unavailable": None,
}

AREAS = [(1, "acre"), (2.5, "acre"), (0.5, "hectare")]

REC, ABS, DELAY = "recommend", "abstain", "delay"


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def pct(num: float, den: float) -> float | None:
    return round(num / den, 4) if den else None


def stage_key(stage: str) -> str:
    stage = stage.strip().lower().replace(" ", "_")
    return STAGE_GROUP.get(stage, stage)


@contextmanager
def patched_weather(kind: str):
    """Replace the live weather call used by the advisory router."""
    import app.routers.advisory as advisory

    original = advisory.get_location_weather

    def fake(**_):
        data = WEATHER[kind]
        if data is None:
            raise WeatherServiceError("synthetic outage")
        return {"weather": data, "source": "synthetic"}

    advisory.get_location_weather = fake
    try:
        yield
    finally:
        advisory.get_location_weather = original


def call_advisory(db: Session, row: RegistryEntry, sc: dict, weather: str | None = None) -> Any:
    from app.routers.advisory import get_advisory

    request = AdvisoryRequest(
        crop=row.crop,
        pest=row.pest,
        field_area=sc["area"],
        area_unit=sc["unit"],
        expected_harvest_days=sc["harvest_days"],
        state="Tamil Nadu",
        district="Coimbatore",
        growth_stage=sc.get("stage"),
        previous_application_count=sc.get("prev_count"),
        days_since_last_application=sc.get("days_since"),
    )
    with patched_weather(weather or sc["weather"]):
        return get_advisory(request, db)


# ----------------------------------------------------------------------------
# independent oracle
# ----------------------------------------------------------------------------

def oracle(row: RegistryEntry, stage_rule, hist_rule, sc: dict) -> dict:
    """Expected outcome from the stored rows, written independently of the engine."""
    reasons = []
    if not row.phi_not_applicable:
        if row.phi_days is None:
            reasons.append("phi_missing")
        elif sc["harvest_days"] < row.phi_days:
            reasons.append("inside_phi")
    if sc.get("stage") is not None and stage_rule is not None:
        allowed = {s.strip().lower().replace(" ", "_") for s in stage_rule.allowed_stages.split(";") if s.strip()}
        if stage_key(sc["stage"]) not in allowed:
            reasons.append("stage_not_allowed")
    count = sc.get("prev_count")
    if count is not None and hist_rule is not None and hist_rule.max_applications is not None:
        if count >= hist_rule.max_applications:
            reasons.append("max_applications")
        gap = hist_rule.min_interval_days
        if count > 0 and gap is not None:
            if sc.get("days_since") is None or sc["days_since"] < gap:
                reasons.append("interval")
    if reasons:
        return {"status": ABS, "dose": None, "reasons": reasons}
    weather = WEATHER[sc["weather"]]
    if weather is None:
        return {"status": ABS, "dose": None, "reasons": ["weather_unavailable"]}
    windy = weather["max_wind_speed_m_s"] >= WIND_LIMIT
    rainy = weather["max_rain_probability"] >= RAIN_PROB_LIMIT and weather["rain_total_mm"] >= RAIN_MM_LIMIT
    if windy or rainy:
        return {"status": DELAY, "dose": None, "reasons": ["weather"]}
    dose = round(row.dose_min_per_hectare * sc["area"] * HECTARES[sc["unit"]], 2)
    return {"status": REC, "dose": dose, "reasons": []}


def find_rules(db: Session, row: RegistryEntry):
    stage = (
        db.query(GrowthStageRule)
        .filter(GrowthStageRule.crop.ilike(row.crop), GrowthStageRule.pest.ilike(row.pest),
                GrowthStageRule.active_ingredient.ilike(row.active_ingredient), GrowthStageRule.verified.is_(True))
        .first()
    )
    hist = (
        db.query(TreatmentHistoryRule)
        .filter(TreatmentHistoryRule.crop.ilike(row.crop), TreatmentHistoryRule.pest.ilike(row.pest),
                TreatmentHistoryRule.active_ingredient.ilike(row.active_ingredient),
                TreatmentHistoryRule.verified.is_(True))
        .all()
    )
    return stage, (hist[0] if len(hist) == 1 else None)


def usable_rows(db: Session) -> tuple[list[RegistryEntry], int]:
    """One row per crop+pest key that the advisory endpoint can resolve to a single candidate."""
    rows = (
        db.query(RegistryEntry)
        .filter(RegistryEntry.verified.is_(True), RegistryEntry.is_test_data.is_(False))
        .order_by(RegistryEntry.crop, RegistryEntry.id)
        .all()
    )
    groups: dict[tuple[str, str], list[RegistryEntry]] = {}
    for row in rows:
        groups.setdefault((row.crop.lower(), row.pest.lower()), []).append(row)
    singles = [g[0] for g in groups.values() if len(g) == 1]
    return singles, len(groups) - len(singles)


def build_scenarios(row: RegistryEntry, stage_rule, hist_rule) -> list[dict]:
    harvests = {1000}
    if row.phi_days and row.phi_days > 0 and not row.phi_not_applicable:
        harvests |= {row.phi_days - 1, row.phi_days}
    stages: list[str | None] = [None]
    if stage_rule is not None:
        allowed = {s.strip().lower().replace(" ", "_") for s in stage_rule.allowed_stages.split(";") if s.strip()}
        ok = [s for s in ("seedling", "vegetative", "flowering", "fruiting", "pre_harvest") if stage_key(s) in allowed]
        bad = [s for s in ("seedling", "vegetative", "flowering", "fruiting", "pre_harvest") if stage_key(s) not in allowed]
        if ok:
            stages.append(ok[0])
        if bad:
            stages.append(bad[0])
    histories: list[tuple[int | None, int | None]] = [(None, None)]
    if hist_rule is not None and hist_rule.max_applications is not None:
        top, gap = hist_rule.max_applications, hist_rule.min_interval_days
        histories += [(0, None), (top, None)]
        if top - 1 > 0 and gap is not None:
            histories += [(top - 1, int(gap)), (top - 1, max(int(gap) - 1, 0))]
        elif top - 1 > 0:
            histories.append((top - 1, None))
    out = []
    for (area, unit), harvest, stage, (cnt, days), weather in itertools.product(
        AREAS, sorted(harvests), stages, histories, ("safe", "rain", "wind", "unavailable")
    ):
        out.append({"area": area, "unit": unit, "harvest_days": harvest, "stage": stage,
                    "prev_count": cnt, "days_since": days, "weather": weather})
    return out


# ----------------------------------------------------------------------------
# metrics
# ----------------------------------------------------------------------------

def score(records: list[dict]) -> dict:
    """records: expected_status, actual_status, expected_dose, actual_dose."""
    n = len(records)
    unsafe = [r for r in records if r["expected_status"] != REC]
    safe = [r for r in records if r["expected_status"] == REC]
    violations = [r for r in unsafe if r["actual_status"] == REC]
    non_rec_actual = [r for r in records if r["actual_status"] != REC]
    correct_abstain = [r for r in non_rec_actual if r["expected_status"] != REC]
    caught = [r for r in unsafe if r["actual_status"] != REC]
    both_rec = [r for r in safe if r["actual_status"] == REC]
    dose_ok = [r for r in both_rec if r["actual_dose"] is not None and abs(r["actual_dose"] - r["expected_dose"]) <= 0.01]
    phi_cases = [r for r in records if "inside_phi" in r.get("reasons", [])]
    return {
        "scenarios": n,
        "unsafe_scenarios": len(unsafe),
        "decision_accuracy_3class": pct(sum(r["expected_status"] == r["actual_status"] for r in records), n),
        "decision_accuracy_rec_vs_not": pct(sum((r["expected_status"] == REC) == (r["actual_status"] == REC) for r in records), n),
        "safety_violations": len(violations),
        "safety_compliance_rate": pct(len(unsafe) - len(violations), len(unsafe)),
        "abstention_precision": pct(len(correct_abstain), len(non_rec_actual)),
        "abstention_recall": pct(len(caught), len(unsafe)),
        "unnecessary_abstentions": sum(1 for r in safe if r["actual_status"] != REC),
        "dose_accuracy": pct(len(dose_ok), len(both_rec)),
        "dose_cases": len(both_rec),
        "phi_cases": len(phi_cases),
        "phi_compliance": pct(sum(r["actual_status"] != REC for r in phi_cases), len(phi_cases)),
    }


def lat_stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {"n": len(values), "mean_ms": round(statistics.mean(values), 2),
            "p50_ms": round(ordered[len(ordered) // 2], 2),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
            "max_ms": round(ordered[-1], 2)}


# ----------------------------------------------------------------------------
# baselines (SIMULATED) and ablations
# ----------------------------------------------------------------------------

def baseline_b2(row: RegistryEntry, sc: dict) -> tuple[str, float | None]:
    """Registry lookup only: always answers with the per-hectare dose, no farmer context."""
    return REC, round(row.dose_min_per_hectare, 2)


def baseline_b3(row: RegistryEntry, sc: dict) -> tuple[str, float | None]:
    """Dose calculator: scales by area and checks PHI. Ignores stage, history and weather."""
    if not row.phi_not_applicable and (row.phi_days is None or sc["harvest_days"] < row.phi_days):
        return ABS, None
    return REC, round(row.dose_min_per_hectare * sc["area"] * HECTARES[sc["unit"]], 2)


def baseline_b1(ask: Callable[[str], str | None], row: RegistryEntry, sc: dict) -> tuple[str, float | None] | None:
    """Direct LLM: sees the same scenario as text and no rule engine. Returns None when no answer."""
    prompt = (
        "You are a farm advisor. Answer with JSON only: "
        '{"decision": "recommend" | "abstain" | "delay", "dose": number or null, "unit": string or null}.\n'
        f"Crop: {row.crop}. Pest: {row.pest}. Field: {sc['area']} {sc['unit']}. "
        f"Harvest in {sc['harvest_days']} days. Growth stage: {sc.get('stage') or 'unknown'}. "
        f"Previous applications: {sc.get('prev_count') if sc.get('prev_count') is not None else 'unknown'}. "
        f"Days since last: {sc.get('days_since') if sc.get('days_since') is not None else 'unknown'}. "
        f"Weather next 24 h: {WEATHER[sc['weather']] or 'forecast unavailable'}."
    )
    reply = ask(prompt)
    if not reply:
        return None
    try:
        start, end = reply.index("{"), reply.rindex("}") + 1
        data = json.loads(reply[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
    decision = str(data.get("decision", "")).lower()
    if decision not in (REC, ABS, DELAY):
        return None
    dose = data.get("dose")
    return decision, (round(float(dose), 2) if isinstance(dose, (int, float)) else None)


def llm_ask() -> Callable[[str], str | None] | None:
    from app.services import llm_service

    if not llm_service.is_active():
        return None
    return lambda prompt: llm_service._chat([{"role": "user", "content": prompt}], max_tokens=120)


# ----------------------------------------------------------------------------
# core grid
# ----------------------------------------------------------------------------

def run_grid(db: Session, b1_sample: int = 40, ask: Callable[[str], str | None] | None = None,
             per_key_cap: int | None = None, progress: Callable[[str], None] | None = None) -> dict:
    """per_key_cap: keep at most this many scenarios per registry key (seeded random sample, seed 0)."""
    import random

    rows, multi = usable_rows(db)
    full_total = sampled_total = 0
    started_at = time.perf_counter()
    systems: dict[str, list[dict]] = {k: [] for k in (
        "proposed", "B2_registry_only_simulated", "B3_calculator_simulated",
        "abl_no_weather", "abl_no_phi", "abl_no_history", "abl_no_stage", "abl_no_area",
        "abl_no_abstention_simulated", "abl_no_farmer_context")}
    b1_records: list[dict] = []
    detail: list[dict] = []
    latencies: list[float] = []
    grounding_total = grounding_ok = 0
    ask = ask if ask is not None else llm_ask()
    b1_budget = b1_sample

    for index, row in enumerate(rows, 1):
        stage_rule, hist_rule = find_rules(db, row)
        scenarios = build_scenarios(row, stage_rule, hist_rule)
        full_total += len(scenarios)
        if per_key_cap is not None and len(scenarios) > per_key_cap:
            scenarios = random.Random(f"{row.crop}|{row.pest}").sample(scenarios, per_key_cap)
        sampled_total += len(scenarios)
        if progress:
            progress(f"  grid {index}/{len(rows)} {row.crop} / {row.pest}: {len(scenarios)} scenarios, {time.perf_counter() - started_at:.0f}s elapsed")
        for sc in scenarios:
            exp = oracle(row, stage_rule, hist_rule, sc)
            base = {"expected_status": exp["status"], "expected_dose": exp["dose"], "reasons": exp["reasons"]}

            started = time.perf_counter()
            res = call_advisory(db, row, sc)
            latencies.append((time.perf_counter() - started) * 1000)
            systems["proposed"].append({**base, "actual_status": res.status, "actual_dose": res.scaled_dose_min})
            detail.append({"crop": row.crop, "pest": row.pest, "area": f"{sc['area']} {sc['unit']}",
                           "harvest_days": sc["harvest_days"], "stage": sc["stage"] or "",
                           "prev_count": "" if sc["prev_count"] is None else sc["prev_count"],
                           "days_since": "" if sc["days_since"] is None else sc["days_since"],
                           "weather": sc["weather"], "expected": exp["status"], "expected_dose": exp["dose"],
                           "actual": res.status, "actual_dose": res.scaled_dose_min,
                           "pass": exp["status"] == res.status and (exp["dose"] is None or abs((res.scaled_dose_min or -1) - exp["dose"]) <= 0.01),
                           "fired_rules": ";".join(res.fired_rules)})
            if res.status == REC:
                grounding_total += 1
                lo, hi = res.scaled_dose_min, res.scaled_dose_max
                per_ha_ok = res.active_ingredient == row.active_ingredient and res.dose_unit == row.dose_unit
                range_ok = lo is not None and abs(lo - round(row.dose_min_per_hectare * sc["area"] * HECTARES[sc["unit"]], 2)) <= 0.01
                grounding_ok += int(per_ha_ok and range_ok and bool(res.registry_verified))

            for name, fn in (("B2_registry_only_simulated", baseline_b2), ("B3_calculator_simulated", baseline_b3)):
                status, dose = fn(row, sc)
                systems[name].append({**base, "actual_status": status, "actual_dose": dose})

            # ablations on the real engine: remove one context source
            def abl(name, sc2, weather=None):
                r2 = call_advisory(db, row, sc2, weather)
                systems[name].append({**base, "actual_status": r2.status, "actual_dose": r2.scaled_dose_min})

            abl("abl_no_weather", sc, "safe")
            abl("abl_no_phi", {**sc, "harvest_days": 1000})
            abl("abl_no_history", {**sc, "prev_count": None, "days_since": None})
            abl("abl_no_stage", {**sc, "stage": None})
            abl("abl_no_area", {**sc, "area": 1, "unit": "hectare"})
            abl("abl_no_farmer_context", {**sc, "area": 1, "unit": "hectare", "harvest_days": 1000,
                                           "stage": None, "prev_count": None, "days_since": None}, "safe")
            # no abstention (simulated): every block is overridden into a dose
            systems["abl_no_abstention_simulated"].append(
                {**base, "actual_status": REC,
                 "actual_dose": round(row.dose_min_per_hectare * sc["area"] * HECTARES[sc["unit"]], 2)})

            if ask is not None and b1_budget > 0:
                b1_budget -= 1
                out = baseline_b1(ask, row, sc)
                if out is not None:
                    b1_records.append({**base, "actual_status": out[0], "actual_dose": out[1]})

    metrics = {name: score(recs) for name, recs in systems.items()}
    b1 = {"status": "NOT RUN: no LLM key configured (set LLM_ENABLED=true and LLM_API_KEY)"}
    if ask is not None:
        b1 = {"status": "run", "sample": b1_sample, "answered": len(b1_records), **score(b1_records)} if b1_records else \
             {"status": "run but no parsable answers"}
    return {
        "registry_rows_used": len(rows),
        "scenarios_full_grid": full_total,
        "scenarios_sampled": sampled_total if per_key_cap is not None else None,
        "per_key_cap": per_key_cap,
        "keys_skipped_multiple_candidates": multi,
        "scenarios": len(systems["proposed"]),
        "metrics": metrics,
        "b1_direct_llm": b1,
        "grounding": {"issued_recommendations": grounding_total, "traceable": grounding_ok,
                      "rate": pct(grounding_ok, grounding_total)},
        "latency_engine": lat_stats(latencies),
        "detail": detail,
    }


# ----------------------------------------------------------------------------
# gold utterances: tool-argument accuracy and multilingual consistency
# ----------------------------------------------------------------------------

# Written by hand, independent of the lexicon file. crop/pest are canonical names.
GOLD = [
    ("en", "My rice has blast, 2 acres, harvest in 30 days",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 2.0, "land_unit": "acre", "harvest_days": 30}),
    ("en", "paddy leaf blast on 1.5 hectares, I will harvest after 45 days",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 1.5, "land_unit": "hectare", "harvest_days": 45}),
    ("en", "chilli thrips in 3 acre field, harvest in 10 days",
     {"crop": "Chilli", "land_area": 3.0, "land_unit": "acre", "harvest_days": 10}),
    ("en", "banana sigatoka, 20 cents of land",
     {"crop": "Banana", "pest_canonical": "Sigatoka", "land_area": 20.0, "land_unit": "cent"}),
    ("en", "rice blast 10 guntha harvest in 20 days",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 10.0, "land_unit": "guntha", "harvest_days": 20}),
    ("en", "my paddy has neck blast, field is 4 acres",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 4.0, "land_unit": "acre"}),
    ("hi", "धान में झोंका रोग, 2 एकड़, कटाई में 30 दिन",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 2.0, "land_unit": "acre", "harvest_days": 30}),
    ("hi", "मेरे धान में ब्लास्ट है, 3 एकड़ खेत",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 3.0, "land_unit": "acre"}),
    ("hi", "धान में झोंका, 1 हेक्टेयर, कटाई 20 दिन में",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 1.0, "land_unit": "hectare", "harvest_days": 20}),
    ("ta", "நெல்லில் குலை நோய், 2 ஏக்கர், அறுவடைக்கு 30 நாட்கள்",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 2.0, "land_unit": "acre", "harvest_days": 30}),
    ("ta", "என் நெல் வயலில் குலைநோய், 5 ஏக்கர்",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 5.0, "land_unit": "acre"}),
    ("ta", "நெல்லில் குலை நோய், 1 ஹெக்டேர், அறுவடைக்கு 40 நாட்கள்",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 1.0, "land_unit": "hectare", "harvest_days": 40}),
    ("te", "వరిలో అగ్గి తెగులు, 2 ఎకరాలు, కోతకు 30 రోజులు",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 2.0, "land_unit": "acre", "harvest_days": 30}),
    ("te", "నా వరి పొలంలో అగ్గి తెగులు ఉంది, 3 ఎకరాలు",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 3.0, "land_unit": "acre"}),
    ("te", "వరిలో అగ్గి తెగులు, 1 హెక్టారు, కోతకు 15 రోజులు",
     {"crop": "Rice", "pest_canonical": "Blast", "land_area": 1.0, "land_unit": "hectare", "harvest_days": 15}),
]


def tool_argument_accuracy() -> dict:
    from app.services.context_extraction_service import extract_context

    per_field: dict[str, list[bool]] = {}
    rows = []
    exact = 0
    for language, text, gold in GOLD:
        got = extract_context(text)
        fields_ok = {}
        for key, expected in gold.items():
            actual = getattr(got, key)
            ok = (abs(actual - expected) < 1e-9) if isinstance(expected, float) and actual is not None else actual == expected
            fields_ok[key] = ok
            per_field.setdefault(key, []).append(ok)
        exact += all(fields_ok.values())
        rows.append({"language": language, "text": text, "all_correct": all(fields_ok.values()),
                     "wrong_fields": [k for k, v in fields_ok.items() if not v]})
    by_language: dict[str, dict] = {}
    for r, (language, _, gold) in zip(rows, GOLD):
        entry = by_language.setdefault(language, {"utterances": 0, "exact": 0})
        entry["utterances"] += 1
        entry["exact"] += int(r["all_correct"])
    return {
        "utterances": len(GOLD),
        "exact_match_rate": pct(exact, len(GOLD)),
        "field_accuracy": {k: pct(sum(v), len(v)) for k, v in per_field.items()},
        "by_language": by_language,
        "failures": [r for r in rows if not r["all_correct"]],
    }


# ----------------------------------------------------------------------------
# chat-level checks
# ----------------------------------------------------------------------------

CHAT_PREFERRED = [("rice", "blast"), ("chilli", "thrips"), ("banana", "sigatoka")]

# Per-language opening turn for the same case, then English-independent follow-up answers.
CHAT_CASE = {
    "en": ["My rice has blast", "Coimbatore, Tamil Nadu", "2 acres", "30", "flowering", "no"],
    "hi": ["मेरे धान में झोंका रोग है", "Coimbatore, Tamil Nadu", "2 एकड़", "30", "फूल", "नहीं"],
    "ta": ["நெல்லில் குலை நோய்", "Coimbatore, Tamil Nadu", "2 ஏக்கர்", "30", "பூக்கும்", "இல்லை"],
    "te": ["వరిలో అగ్గి తెగులు", "Coimbatore, Tamil Nadu", "2 ఎకరాలు", "30", "పుష్పించే", "లేదు"],
}
DISTRACTORS = [
    "Hello, good morning",
    "My cousin lives in Madurai and grows sugarcane",
    "The festival is next week and it was a good market year",
]


@contextmanager
def offline():
    """No network during the evaluation: no geocoding, no soil lookup, no live weather.

    A configured OpenWeather key would otherwise trigger real place lookups and
    SoilGrids requests on every chat turn, which is slow and not reproducible."""
    import app.routers.advisory as advisory
    from app.services import weather_service

    saved_key = weather_service.OPENWEATHER_API_KEY
    saved_soil = advisory.get_root_zone_soil_context

    def no_soil(**_):
        raise advisory.SoilServiceError("soil lookup disabled during evaluation")

    weather_service.OPENWEATHER_API_KEY = None
    advisory.get_root_zone_soil_context = no_soil
    try:
        yield
    finally:
        weather_service.OPENWEATHER_API_KEY = saved_key
        advisory.get_root_zone_soil_context = saved_soil


@contextmanager
def chat_client(factory: sessionmaker):
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.main import app

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def _converse(client, lines: list[str], language: str = "auto", new_session_each_turn: bool = False) -> tuple[dict, list[float]]:
    session, reply, times = None, {}, []
    for line in lines:
        started = time.perf_counter()
        response = client.post("/api/chat/message", json={
            "session_id": None if new_session_each_turn else session, "text": line, "language": language})
        times.append((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            return {"decision": f"HTTP_{response.status_code}"}, times
        reply = response.json()
        session = reply["session_id"]
    return reply, times


def _signature(reply: dict) -> tuple:
    adv = reply.get("advisory") or {}
    return (reply.get("decision"), adv.get("status"), adv.get("active_ingredient"), adv.get("scaled_dose_min"))


def chat_checks(factory: sessionmaker) -> dict:
    out: dict[str, Any] = {}
    with offline(), patched_weather("safe"), chat_client(factory) as client:
        base_reply, base_times = _converse(client, CHAT_CASE["en"])
        base = _signature(base_reply)
        out["reference_case"] = {"signature": list(base), "note": "English rice blast, 2 acres, 30 days, flowering, no history, synthetic safe weather"}
        if base[0] != "ANSWER":
            out["status"] = ("NOT RUN: the reference English conversation did not reach an ANSWER on this database "
                             "(rice blast row missing or growth-stage rule excludes flowering). Chat checks skipped.")
            return out
        turn_times = list(base_times)

        # 7 irrelevant-context stability: insert a distractor before the last turn
        stable = 0
        for distractor in DISTRACTORS:
            lines = CHAT_CASE["en"][:-1] + [distractor] + CHAT_CASE["en"][-1:]
            reply, times = _converse(client, lines)
            turn_times += times
            # the distractor turn may re-ask the pending question; send the answer again if so
            if reply.get("decision") != "ANSWER":
                reply, times = _converse(client, CHAT_CASE["en"][:-1] + [distractor, CHAT_CASE["en"][-1]])
            stable += int(_signature(reply) == base)
        out["irrelevant_context_stability"] = {"cases": len(DISTRACTORS), "same_answer": stable, "rate": pct(stable, len(DISTRACTORS))}

        # 8 multilingual consistency
        langs = {}
        consistent = 0
        for lang, lines in CHAT_CASE.items():
            reply, times = _converse(client, lines)
            turn_times += times
            sig = _signature(reply)
            langs[lang] = {"signature": list(sig), "same_as_english": sig == base}
            consistent += int(sig == base)
        out["multilingual_consistency"] = {"languages": len(CHAT_CASE), "same_as_english": consistent,
                                           "rate": pct(consistent, len(CHAT_CASE)), "detail": langs}

        # ablation: no memory (every turn starts a new session)
        reply, _ = _converse(client, CHAT_CASE["en"], new_session_each_turn=True)
        out["ablation_no_memory"] = {"decision": reply.get("decision"), "reaches_answer": reply.get("decision") == "ANSWER",
                                     "note": "each turn sent without the session id"}

        # ablation: no verified-evidence retrieval
        import app.services.rag_service as rag

        original = rag.retrieve_verified_evidence
        rag.retrieve_verified_evidence = lambda **_: {"status": "no_evidence", "results": []}
        try:
            reply, _ = _converse(client, CHAT_CASE["en"])
        finally:
            rag.retrieve_verified_evidence = original
        out["ablation_no_retrieval"] = {"signature": list(_signature(reply)), "same_decision_and_dose": _signature(reply) == base}
        out["latency_chat_turn"] = lat_stats(turn_times)
    out["status"] = "run"
    return out


# ----------------------------------------------------------------------------
# retrieval
# ----------------------------------------------------------------------------

def retrieval_hit_at_k(knowledge_base_path: Path | None = None, ks=(1, 3, 5)) -> dict:
    """Self-derived queries: each verified record is asked for by its crop and topic.

    This measures retrievability of the stored records. It is NOT a measure of
    answer quality on free-form farmer questions (that needs human-written gold).
    """
    from app.services import rag_service

    try:
        records = rag_service.load_verified_knowledge(knowledge_base_path)
    except FileNotFoundError:
        return {"status": "NOT RUN: knowledge base file not found"}
    except Exception as exc:  # unreadable file
        return {"status": f"NOT RUN: {exc.__class__.__name__}"}
    cases = [r for r in records if r.get("id") is not None and r.get("topic") and r.get("crop")]
    if not cases:
        return {"status": "NOT RUN: no verified records with id, crop and topic"}
    hits = {k: 0 for k in ks}
    ranks = []
    for record in cases:
        result = rag_service.retrieve_verified_evidence(
            query=str(record["topic"]), crop=record["crop"], top_k=max(ks), knowledge_base_path=knowledge_base_path)
        ids = [item.get("id") for item in result.get("results", [])]
        rank = ids.index(record["id"]) + 1 if record["id"] in ids else None
        ranks.append(rank)
        for k in ks:
            hits[k] += int(rank is not None and rank <= k)
    mrr = statistics.mean((1 / r) if r else 0 for r in ranks)
    return {"status": "run", "queries": len(cases), "query_source": "record topic + crop (self-derived)",
            **{f"hit@{k}": pct(hits[k], len(cases)) for k in ks}, "mrr": round(mrr, 4)}


# ----------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------

def fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_markdown(result: dict) -> str:
    m = result["grid"]["metrics"]
    lines = [
        "# Research evaluation",
        "",
        f"Registry keys used: {result['grid']['registry_rows_used']} (skipped, multiple candidates: "
        f"{result['grid']['keys_skipped_multiple_candidates']}). Scenarios run: {result['grid']['scenarios']}"
        + (f" (random sample, seed fixed, at most {result['grid']['per_key_cap']} per key, from {result['grid']['scenarios_full_grid']} in the full grid; use --full for all)." if result["grid"].get("per_key_cap") else " (full grid)."),
        "Weather is a fixed synthetic forecast. The oracle restates the stored rules independently of the engine.",
        "B2 and B3 are simulated rule-based baselines written for this script, not real systems.",
        "",
        "## Proposed system against the oracle",
        "",
    ]
    p = m["proposed"]
    for key in ("decision_accuracy_3class", "decision_accuracy_rec_vs_not", "safety_compliance_rate", "safety_violations",
                "abstention_precision", "abstention_recall", "unnecessary_abstentions", "dose_accuracy", "phi_compliance"):
        lines.append(f"- {key}: {fmt(p[key])}")
    lines += ["", "## Baselines", "", "| system | safety compliance | violations | abstention recall | dose accuracy |", "|---|---|---|---|---|"]
    for name in ("proposed", "B2_registry_only_simulated", "B3_calculator_simulated"):
        s = m[name]
        lines.append(f"| {name} | {fmt(s['safety_compliance_rate'])} | {s['safety_violations']} | {fmt(s['abstention_recall'])} | {fmt(s['dose_accuracy'])} |")
    b1 = result["grid"]["b1_direct_llm"]
    lines.append(f"| B1_direct_llm | {fmt(b1.get('safety_compliance_rate'))} | {fmt(b1.get('safety_violations'))} | {fmt(b1.get('abstention_recall'))} | {fmt(b1.get('dose_accuracy'))} |")
    lines += ["", f"B1 status: {b1.get('status')}", "", "## Ablations (scored against the full-context oracle)", "",
              "| removed | safety compliance | violations | decision accuracy | dose accuracy |", "|---|---|---|---|---|"]
    for name in [k for k in m if k.startswith("abl_")]:
        s = m[name]
        lines.append(f"| {name[4:]} | {fmt(s['safety_compliance_rate'])} | {s['safety_violations']} | {fmt(s['decision_accuracy_3class'])} | {fmt(s['dose_accuracy'])} |")
    g = result["grid"]["grounding"]
    lines += ["", "## Evidence grounding", "",
              f"- issued recommendations: {g['issued_recommendations']}, traceable to a verified registry row and the independent dose: {g['traceable']} ({fmt(g['rate'])})", ""]
    ta = result["tool_arguments"]
    lines += ["## Tool-argument accuracy", "", f"- utterances: {ta['utterances']}, exact match: {fmt(ta['exact_match_rate'])}",
              f"- field accuracy: {ta['field_accuracy']}", f"- by language: {ta['by_language']}"]
    for f in ta["failures"]:
        lines.append(f"- FAIL ({f['language']}) {f['text']} -> wrong fields {f['wrong_fields']}")
    chat = result["chat"]
    lines += ["", "## Chat-level checks", "", f"- status: {chat.get('status')}"]
    for key in ("irrelevant_context_stability", "multilingual_consistency", "ablation_no_memory", "ablation_no_retrieval"):
        if key in chat:
            value = {k: v for k, v in chat[key].items() if k != "detail"}
            lines.append(f"- {key}: {value}")
    r = result["retrieval"]
    lines += ["", "## Retrieval", "", f"- {r}", "", "## Latency", "",
              f"- engine call: {result['grid']['latency_engine']}", f"- chat turn: {chat.get('latency_chat_turn', 'n/a')}", ""]
    lines += ["## Limits", "",
              "- Measures rule compliance and context sensitivity, not agronomic effectiveness.",
              "- Retrieval queries are derived from the stored records, so hit@k shows retrievability only.",
              "- Gold utterances cover rice, chilli and banana in four languages; extend before claiming wider coverage.",
              "- Hindi, Tamil and Telugu wording has not been reviewed by a native speaker.", ""]
    return "\n".join(lines)


def open_eval_session_factory() -> tuple[sessionmaker, Path]:
    """Copy the configured SQLite database to a temp file and open it, leaving the live database untouched."""
    from app.db import Base, engine as live_engine

    source = live_engine.url.database
    temp = Path(tempfile.mkdtemp(prefix="kisansaarthi_eval_")) / "eval.db"
    if source and Path(source).exists():
        shutil.copy2(source, temp)
    copy_engine = create_engine(f"sqlite:///{temp.as_posix()}", connect_args={"check_same_thread": False})
    import app.models_conversation  # noqa: F401
    import app.models_trace  # noqa: F401

    Base.metadata.create_all(bind=copy_engine)
    return sessionmaker(bind=copy_engine, autoflush=False, autocommit=False), temp


def run_all(factory: sessionmaker, knowledge_base_path: Path | None = None, b1_ask=None,
            per_key_cap: int | None = None, progress: Callable[[str], None] | None = None) -> dict:
    if progress:
        progress("Scenario grid (no network)...")
    with factory() as db:
        grid = run_grid(db, ask=b1_ask, per_key_cap=per_key_cap, progress=progress)
    if progress:
        progress("Chat-level checks (no network)...")
    return {
        "grid": grid,
        "tool_arguments": tool_argument_accuracy(),
        "chat": chat_checks(factory),
        "retrieval": retrieval_hit_at_k(knowledge_base_path),
    }


def write_reports(result: dict, out_dir: Path = REPORTS) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    detail = result["grid"].pop("detail")
    columns = list(detail[0].keys()) if detail else ["crop"]
    with (out_dir / "research_eval.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(detail)
    (out_dir / "research_eval.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (out_dir / "research_eval.md").write_text(render_markdown(result), encoding="utf-8")
    result["grid"]["detail"] = detail


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="KisanSaarthi research evaluation")
    parser.add_argument("--full", action="store_true", help="run every scenario (slow on a laptop)")
    parser.add_argument("--cap", type=int, default=60, help="scenarios per registry key when not --full (default 60)")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    factory, temp = open_eval_session_factory()
    with factory() as db:
        if db.query(RegistryEntry).count() == 0:
            print("The verified registry is empty: nothing to evaluate. Import your data first.")
            return
    result = run_all(factory, per_key_cap=None if args.full else args.cap, progress=lambda m: print(m, flush=True))
    write_reports(result)
    print(render_markdown(result))
    print(f"Files: {REPORTS / 'research_eval.md'}, research_eval.csv, research_eval.json")
    shutil.rmtree(temp.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
