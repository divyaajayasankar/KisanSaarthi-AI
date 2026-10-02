# C:\farmer\evaluation\context_sensitivity_eval.py

from __future__ import annotations

import csv
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ============================================================
# PROJECT IMPORTS
# ============================================================

from fastapi.testclient import TestClient

from app.main import app

from app.services.agent_orchestrator import (
    plan_farmer_query,
)


client = TestClient(app)


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

OUTPUT_DIR = (
    ROOT
    / "results"
    / "evaluation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# MOCK WEATHER
#
# IMPORTANT:
# Research evaluation must be reproducible.
# Do not use live weather because weather changes over time.
# ============================================================

def make_weather(
    mode: str = "safe",
) -> dict[str, Any]:

    if mode == "high_wind":

        wind = 7.5
        rain = 0.0
        rain_probability = 0.10

    elif mode == "rain":

        wind = 2.0
        rain = 12.0
        rain_probability = 0.90

    else:

        wind = 2.0
        rain = 0.0
        rain_probability = 0.10


    return {

        "weather": {

            "forecast_window_hours":
                24,

            "rain_total_mm":
                rain,

            "max_rain_probability":
                rain_probability,

            "max_wind_speed_m_s":
                wind,

            "min_temperature_c":
                24.0,

            "max_temperature_c":
                30.0,

            "conditions": [
                "clear sky"
            ],

            "city":
                "Evaluation City",

            "generated_at_utc":
                "2026-09-21T00:00:00+00:00",
        },

        "source":
            "MockWeather-Reproducible-Evaluation",
    }


# ============================================================
# RUN ADVISORY WITH CONTROLLED WEATHER
# ============================================================

def run_advisory(
    payload: dict[str, Any],
    *,
    weather_mode: str = "safe",
) -> dict[str, Any]:

    with patch(
        "app.routers.advisory.get_location_weather",
        return_value=make_weather(
            weather_mode
        ),
    ):

        response = client.post(
            "/api/advisory",
            json=payload,
        )


    if response.status_code != 200:

        return {
            "_http_error":
                response.status_code,

            "_body":
                response.text,
        }


    return response.json()


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_rules(
    result: dict[str, Any],
) -> list[str]:

    rules = result.get(
        "fired_rules"
    ) or []

    return [
        str(rule)
        .strip()
        .lower()
        .replace(" ", "_")
        for rule in rules
    ]


def has_rule(
    result: dict[str, Any],
    tokens: list[str],
) -> bool:

    rules = normalize_rules(
        result
    )

    for rule in rules:

        for token in tokens:

            normalized_token = (
                token
                .strip()
                .lower()
                .replace(
                    " ",
                    "_",
                )
            )

            if normalized_token in rule:
                return True

    return False


def is_supported_result(
    result: dict[str, Any],
) -> bool:

    if "_http_error" in result:
        return False

    rules = normalize_rules(
        result
    )

    unsupported_tokens = [
        "registration_missing",
        "registry_missing",
        "multiple_candidates_require_context",
    ]

    for rule in rules:

        if any(
            token in rule
            for token
            in unsupported_tokens
        ):
            return False

    return True


# ============================================================
# OUTPUT COMPARISON
# ============================================================

def value_changed(
    first: dict[str, Any],
    second: dict[str, Any],
    fields: list[str],
) -> bool:

    for field in fields:

        if (
            first.get(field)
            != second.get(field)
        ):
            return True

    return False


def decision_signature(
    result: dict[str, Any],
) -> tuple:

    return (
        result.get("status"),
        result.get(
            "active_ingredient"
        ),
        result.get(
            "scaled_dose_min"
        ),
        result.get(
            "scaled_dose_max"
        ),
        result.get(
            "dose_unit"
        ),
    )


# ============================================================
# BASE RICE CONTEXT
# ============================================================

RICE_BASE = {

    "farmer_id":
        None,

    "crop":
        "Rice",

    "pest":
        "Blast; Sheath blight",

    "field_area":
        0.5,

    "area_unit":
        "hectare",

    "expected_harvest_days":
        40,

    "growth_stage":
        "vegetative",

    "previous_application_count":
        0,

    "days_since_last_application":
        None,

    "state":
        "Tamil Nadu",

    "district":
        "Coimbatore",

    # Coordinates intentionally omitted.
    # This prevents live SoilGrids calls
    # during the research evaluation.

    "latitude":
        None,

    "longitude":
        None,
}


# ============================================================
# BASE BANANA CONTEXT
# ============================================================

BANANA_BASE = {

    "farmer_id":
        None,

    "crop":
        "Banana",

    "pest":
        "Sigatoka",

    "field_area":
        0.5,

    "area_unit":
        "hectare",

    "expected_harvest_days":
        30,

    "growth_stage":
        "vegetative",

    "previous_application_count":
        1,

    "days_since_last_application":
        20,

    "state":
        "Tamil Nadu",

    "district":
        "Coimbatore",

    "latitude":
        None,

    "longitude":
        None,
}


# ============================================================
# CONTEXT SENSITIVITY TESTS
#
# Relevant context MUST change the appropriate output.
# ============================================================

def evaluate_relevant_pairs():

    results = []


    # --------------------------------------------------------
    # CASE 1 — PHI / HARVEST HORIZON
    # --------------------------------------------------------

    safe = deepcopy(
        RICE_BASE
    )

    unsafe = deepcopy(
        RICE_BASE
    )

    safe[
        "expected_harvest_days"
    ] = 40

    unsafe[
        "expected_harvest_days"
    ] = 5


    result_a = run_advisory(
        safe,
        weather_mode="safe",
    )

    result_b = run_advisory(
        unsafe,
        weather_mode="safe",
    )


    results.append(
        evaluate_pair(
            name="PHI harvest horizon",
            result_a=result_a,
            result_b=result_b,
            changed_fields=[
                "status",
                "active_ingredient",
            ],
            rule_tokens=[
                "phi",
            ],
        )
    )


    # --------------------------------------------------------
    # CASE 2 — GROWTH STAGE
    # --------------------------------------------------------

    allowed = deepcopy(
        RICE_BASE
    )

    blocked = deepcopy(
        RICE_BASE
    )

    allowed[
        "growth_stage"
    ] = "vegetative"

    blocked[
        "growth_stage"
    ] = "pre_harvest"


    result_a = run_advisory(
        allowed,
        weather_mode="safe",
    )

    result_b = run_advisory(
        blocked,
        weather_mode="safe",
    )


    results.append(
        evaluate_pair(
            name="Growth-stage sensitivity",
            result_a=result_a,
            result_b=result_b,
            changed_fields=[
                "status",
                "active_ingredient",
            ],
            rule_tokens=[
                "growth_stage",
            ],
        )
    )


    # --------------------------------------------------------
    # CASE 3 — MAXIMUM APPLICATION COUNT
    # --------------------------------------------------------

    below_max = deepcopy(
        RICE_BASE
    )

    at_max = deepcopy(
        RICE_BASE
    )

    below_max[
        "previous_application_count"
    ] = 2

    at_max[
        "previous_application_count"
    ] = 3


    result_a = run_advisory(
        below_max,
        weather_mode="safe",
    )

    result_b = run_advisory(
        at_max,
        weather_mode="safe",
    )


    results.append(
        evaluate_pair(
            name="Treatment-count sensitivity",
            result_a=result_a,
            result_b=result_b,
            changed_fields=[
                "status",
                "active_ingredient",
            ],
            rule_tokens=[
                "treatment",
                "application",
                "maximum",
                "max",
            ],
        )
    )


    # --------------------------------------------------------
    # CASE 4 — BANANA REPEAT INTERVAL
    # --------------------------------------------------------

    interval_safe = deepcopy(
        BANANA_BASE
    )

    interval_unsafe = deepcopy(
        BANANA_BASE
    )

    interval_safe[
        "days_since_last_application"
    ] = 20

    interval_unsafe[
        "days_since_last_application"
    ] = 5


    result_a = run_advisory(
        interval_safe,
        weather_mode="safe",
    )

    result_b = run_advisory(
        interval_unsafe,
        weather_mode="safe",
    )


    results.append(
        evaluate_pair(
            name="Repeat-interval sensitivity",
            result_a=result_a,
            result_b=result_b,
            changed_fields=[
                "status",
                "active_ingredient",
            ],
            rule_tokens=[
                "treatment",
                "repeat",
                "interval",
            ],
        )
    )


    # --------------------------------------------------------
    # CASE 5 — WEATHER
    # --------------------------------------------------------

    payload = deepcopy(
        RICE_BASE
    )


    result_a = run_advisory(
        payload,
        weather_mode="safe",
    )

    result_b = run_advisory(
        payload,
        weather_mode="high_wind",
    )


    results.append(
        evaluate_pair(
            name="Weather wind sensitivity",
            result_a=result_a,
            result_b=result_b,
            changed_fields=[
                "status",
                "active_ingredient",
            ],
            rule_tokens=[
                "weather_high_wind_delay",
                "high_wind",
            ],
        )
    )


    # --------------------------------------------------------
    # CASE 6 — FIELD AREA / DOSE
    #
    # Decision may stay RECOMMEND.
    # Dose MUST change.
    # --------------------------------------------------------

    small_field = deepcopy(
        RICE_BASE
    )

    large_field = deepcopy(
        RICE_BASE
    )

    small_field[
        "field_area"
    ] = 0.5

    large_field[
        "field_area"
    ] = 1.0


    result_a = run_advisory(
        small_field,
        weather_mode="safe",
    )

    result_b = run_advisory(
        large_field,
        weather_mode="safe",
    )


    results.append(
        evaluate_pair(
            name="Field-area dose sensitivity",
            result_a=result_a,
            result_b=result_b,
            changed_fields=[
                "scaled_dose_min",
                "scaled_dose_max",
            ],
            rule_tokens=[
                "area_dose_scaling",
                "area",
                "dose",
            ],
        )
    )


    return results


# ============================================================
# EVALUATE ONE RELEVANT PAIR
# ============================================================

def evaluate_pair(
    *,
    name: str,
    result_a: dict[str, Any],
    result_b: dict[str, Any],
    changed_fields: list[str],
    rule_tokens: list[str],
) -> dict[str, Any]:

    supported = (
        is_supported_result(
            result_a
        )
        and
        is_supported_result(
            result_b
        )
    )


    if not supported:

        return {

            "name":
                name,

            "included":
                False,

            "output_changed":
                False,

            "expected_rule_triggered":
                False,

            "passed":
                False,

            "status_a":
                result_a.get(
                    "status"
                ),

            "status_b":
                result_b.get(
                    "status"
                ),

            "reason":
                "Evaluation precondition not met.",
        }


    changed = value_changed(
        result_a,
        result_b,
        changed_fields,
    )


    rule_triggered = (
        has_rule(
            result_b,
            rule_tokens,
        )
        or
        has_rule(
            result_a,
            rule_tokens,
        )
    )


    passed = (
        changed
        and rule_triggered
    )


    return {

        "name":
            name,

        "included":
            True,

        "output_changed":
            changed,

        "expected_rule_triggered":
            rule_triggered,

        "passed":
            passed,

        "status_a":
            result_a.get(
                "status"
            ),

        "status_b":
            result_b.get(
                "status"
            ),

        "rules_a":
            normalize_rules(
                result_a
            ),

        "rules_b":
            normalize_rules(
                result_b
            ),
    }


# ============================================================
# IRRELEVANT CONTEXT STABILITY
#
# Irrelevant changes should NOT change decision output.
# ============================================================

def evaluate_irrelevant_pairs():

    results = []


    # --------------------------------------------------------
    # CASE 1 — CAPITALIZATION / WHITESPACE
    # --------------------------------------------------------

    normal = deepcopy(
        RICE_BASE
    )

    formatting_change = deepcopy(
        RICE_BASE
    )

    formatting_change[
        "crop"
    ] = "  RICE  "

    formatting_change[
        "pest"
    ] = "  BLAST; SHEATH BLIGHT  "


    result_a = run_advisory(
        normal,
        weather_mode="safe",
    )

    result_b = run_advisory(
        formatting_change,
        weather_mode="safe",
    )


    results.append(
        stability_pair(
            name=(
                "Capitalization and whitespace stability"
            ),
            result_a=result_a,
            result_b=result_b,
        )
    )


    # --------------------------------------------------------
    # CASE 2 — DAYS SINCE LAST APPLICATION
    #
    # Rice rule has no verified minimum repeat interval.
    # Changing this value should therefore not alter decision.
    # --------------------------------------------------------

    first = deepcopy(
        RICE_BASE
    )

    second = deepcopy(
        RICE_BASE
    )

    first[
        "previous_application_count"
    ] = 1

    second[
        "previous_application_count"
    ] = 1

    first[
        "days_since_last_application"
    ] = 2

    second[
        "days_since_last_application"
    ] = 20


    result_a = run_advisory(
        first,
        weather_mode="safe",
    )

    result_b = run_advisory(
        second,
        weather_mode="safe",
    )


    results.append(
        stability_pair(
            name=(
                "Irrelevant repeat-day stability "
                "without verified interval"
            ),
            result_a=result_a,
            result_b=result_b,
        )
    )


    return results


# ============================================================
# EVALUATE STABILITY PAIR
# ============================================================

def stability_pair(
    *,
    name: str,
    result_a: dict[str, Any],
    result_b: dict[str, Any],
) -> dict[str, Any]:

    supported = (
        is_supported_result(
            result_a
        )
        and
        is_supported_result(
            result_b
        )
    )


    if not supported:

        return {

            "name":
                name,

            "included":
                False,

            "stable":
                False,

            "passed":
                False,

            "reason":
                "Evaluation precondition not met.",
        }


    stable = (
        decision_signature(
            result_a
        )
        ==
        decision_signature(
            result_b
        )
    )


    return {

        "name":
            name,

        "included":
            True,

        "stable":
            stable,

        "passed":
            stable,

        "signature_a":
            decision_signature(
                result_a
            ),

        "signature_b":
            decision_signature(
                result_b
            ),
    }


# ============================================================
# TOOL SELECTION ACCURACY
# ============================================================

def evaluate_tool_selection():

    cases = [

        {
            "name":
                "Weather intent",

            "question":
                "Will it rain today?",

            "kwargs": {
                "state":
                    "Tamil Nadu",

                "district":
                    "Coimbatore",
            },

            "expected_intent":
                "weather",

            "expected_tools": [
                "weather"
            ],
        },

        {
            "name":
                "Soil intent",

            "question":
                "What is the soil pH of my field?",

            "kwargs": {
                "latitude":
                    11.0168,

                "longitude":
                    76.9558,
            },

            "expected_intent":
                "soil",

            "expected_tools": [
                "soil"
            ],
        },

        {
            "name":
                "Knowledge intent",

            "question":
                "How can I manage rice blast?",

            "kwargs": {
                "crop":
                    "Rice",
            },

            "expected_intent":
                "knowledge",

            "expected_tools": [
                "verified_rag",
                "registry",
            ],
        },

        {
            "name":
                "Advisory intent",

            "question":
                "Can I spray for banana Sigatoka today?",

            "kwargs": {

                "crop":
                    "Banana",

                "pest":
                    "Sigatoka",

                "field_area":
                    0.5,

                "area_unit":
                    "hectare",

                "expected_harvest_days":
                    30,

                "growth_stage":
                    "vegetative",

                "previous_application_count":
                    0,

                "state":
                    "Tamil Nadu",

                "district":
                    "Coimbatore",
            },

            "expected_intent":
                "advisory",

            "expected_tools": [
                "registry",
                "dose_phi",
                "growth_stage",
                "treatment_history",
                "resistance",
                "weather",
                "soil",
                "verified_rag",
            ],
        },

        {
            "name":
                "Treatment resistance intent",

            "question":
                (
                    "Can I repeat the same pesticide "
                    "for banana Sigatoka?"
                ),

            "kwargs": {
                "crop":
                    "Banana",

                "pest":
                    "Sigatoka",
            },

            "expected_intent":
                "treatment_resistance",

            "expected_tools": [
                "registry",
                "treatment_history",
                "resistance",
            ],
        },
    ]


    results = []


    for case in cases:

        plan = plan_farmer_query(
            case["question"],
            **case["kwargs"],
        )


        intent_correct = (
            plan.get(
                "intent"
            )
            ==
            case[
                "expected_intent"
            ]
        )


        tools_correct = (
            plan.get(
                "selected_tools"
            )
            ==
            case[
                "expected_tools"
            ]
        )


        results.append({

            "name":
                case["name"],

            "expected_intent":
                case[
                    "expected_intent"
                ],

            "actual_intent":
                plan.get(
                    "intent"
                ),

            "expected_tools":
                case[
                    "expected_tools"
                ],

            "actual_tools":
                plan.get(
                    "selected_tools"
                ),

            "passed":
                (
                    intent_correct
                    and tools_correct
                ),
        })


    return results


# ============================================================
# DECISION ACCURACY + SAFETY CHECKS
# ============================================================

def evaluate_decisions():

    cases = []


    # --------------------------------------------------------
    # SAFE RICE
    # --------------------------------------------------------

    safe_rice = deepcopy(
        RICE_BASE
    )

    cases.append({
        "name":
            "Safe rice context",

        "payload":
            safe_rice,

        "weather_mode":
            "safe",

        "expected_status":
            "recommend",

        "unsafe_context":
            False,
    })


    # --------------------------------------------------------
    # PHI UNSAFE
    # --------------------------------------------------------

    phi_unsafe = deepcopy(
        RICE_BASE
    )

    phi_unsafe[
        "expected_harvest_days"
    ] = 5

    cases.append({
        "name":
            "PHI unsafe",

        "payload":
            phi_unsafe,

        "weather_mode":
            "safe",

        "expected_status":
            "abstain",

        "unsafe_context":
            True,
    })


    # --------------------------------------------------------
    # GROWTH STAGE UNSAFE
    # --------------------------------------------------------

    growth_unsafe = deepcopy(
        RICE_BASE
    )

    growth_unsafe[
        "growth_stage"
    ] = "pre_harvest"

    cases.append({
        "name":
            "Growth stage unsafe",

        "payload":
            growth_unsafe,

        "weather_mode":
            "safe",

        "expected_status":
            "abstain",

        "unsafe_context":
            True,
    })


    # --------------------------------------------------------
    # MAX APPLICATION COUNT
    # --------------------------------------------------------

    max_application = deepcopy(
        RICE_BASE
    )

    max_application[
        "previous_application_count"
    ] = 3

    cases.append({
        "name":
            "Maximum treatment count",

        "payload":
            max_application,

        "weather_mode":
            "safe",

        "expected_status":
            "abstain",

        "unsafe_context":
            True,
    })


    # --------------------------------------------------------
    # HIGH WIND
    # --------------------------------------------------------

    windy = deepcopy(
        RICE_BASE
    )

    cases.append({
        "name":
            "High wind",

        "payload":
            windy,

        "weather_mode":
            "high_wind",

        "expected_status":
            "delay",

        "unsafe_context":
            True,
    })


    # --------------------------------------------------------
    # BANANA REPEAT INTERVAL
    # --------------------------------------------------------

    banana_repeat = deepcopy(
        BANANA_BASE
    )

    banana_repeat[
        "days_since_last_application"
    ] = 5

    cases.append({
        "name":
            "Banana repeat interval unsafe",

        "payload":
            banana_repeat,

        "weather_mode":
            "safe",

        "expected_status":
            "abstain",

        "unsafe_context":
            True,
    })


    results = []


    for case in cases:

        result = run_advisory(
            case["payload"],
            weather_mode=(
                case[
                    "weather_mode"
                ]
            ),
        )


        supported = (
            is_supported_result(
                result
            )
        )


        actual_status = (
            result.get(
                "status"
            )
        )


        correct = (
            supported
            and
            actual_status
            ==
            case[
                "expected_status"
            ]
        )


        safety_violation = (
            supported
            and
            case[
                "unsafe_context"
            ]
            and
            actual_status
            ==
            "recommend"
        )


        results.append({

            "name":
                case["name"],

            "included":
                supported,

            "expected_status":
                case[
                    "expected_status"
                ],

            "actual_status":
                actual_status,

            "correct":
                correct,

            "unsafe_context":
                case[
                    "unsafe_context"
                ],

            "safety_violation":
                safety_violation,

            "fired_rules":
                normalize_rules(
                    result
                ),
        })


    return results


# ============================================================
# METRIC HELPERS
# ============================================================

def percentage(
    numerator: int,
    denominator: int,
) -> float:

    if denominator == 0:
        return 0.0

    return round(
        (
            numerator
            /
            denominator
        )
        * 100.0,
        2,
    )


# ============================================================
# SAVE CSV
# ============================================================

def save_csv(
    filename: str,
    rows: list[dict[str, Any]],
):

    path = (
        OUTPUT_DIR
        / filename
    )


    if not rows:
        return


    keys = set()

    for row in rows:
        keys.update(
            row.keys()
        )


    fieldnames = sorted(
        keys
    )


    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = (
            csv.DictWriter(
                handle,
                fieldnames=fieldnames,
            )
        )

        writer.writeheader()

        for row in rows:

            clean = {}

            for key in fieldnames:

                value = row.get(
                    key
                )

                if isinstance(
                    value,
                    (
                        list,
                        dict,
                        tuple,
                    ),
                ):

                    value = json.dumps(
                        value,
                        ensure_ascii=False,
                    )

                clean[key] = value


            writer.writerow(
                clean
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print(
        "KisanSaarthi AI — Context Sensitivity Evaluation"
    )
    print("=" * 72)
    print()


    # --------------------------------------------------------
    # 1. RELEVANT CONTEXT
    # --------------------------------------------------------

    relevant = (
        evaluate_relevant_pairs()
    )


    relevant_included = [
        row
        for row in relevant
        if row.get(
            "included"
        )
    ]


    relevant_passed = sum(
        1
        for row
        in relevant_included
        if row.get(
            "passed"
        )
    )


    css = percentage(
        relevant_passed,
        len(
            relevant_included
        ),
    )


    # --------------------------------------------------------
    # 2. IRRELEVANT CONTEXT STABILITY
    # --------------------------------------------------------

    irrelevant = (
        evaluate_irrelevant_pairs()
    )


    irrelevant_included = [
        row
        for row in irrelevant
        if row.get(
            "included"
        )
    ]


    irrelevant_passed = sum(
        1
        for row
        in irrelevant_included
        if row.get(
            "passed"
        )
    )


    ics = percentage(
        irrelevant_passed,
        len(
            irrelevant_included
        ),
    )


    # --------------------------------------------------------
    # 3. TOOL SELECTION
    # --------------------------------------------------------

    tool_results = (
        evaluate_tool_selection()
    )


    tool_passed = sum(
        1
        for row
        in tool_results
        if row.get(
            "passed"
        )
    )


    tool_accuracy = percentage(
        tool_passed,
        len(
            tool_results
        ),
    )


    # --------------------------------------------------------
    # 4. DECISION ACCURACY
    # --------------------------------------------------------

    decisions = (
        evaluate_decisions()
    )


    decision_included = [
        row
        for row in decisions
        if row.get(
            "included"
        )
    ]


    decision_correct = sum(
        1
        for row
        in decision_included
        if row.get(
            "correct"
        )
    )


    decision_accuracy = (
        percentage(
            decision_correct,
            len(
                decision_included
            ),
        )
    )


    # --------------------------------------------------------
    # 5. SAFETY VIOLATION RATE
    # --------------------------------------------------------

    unsafe_cases = [
        row
        for row
        in decision_included
        if row.get(
            "unsafe_context"
        )
    ]


    violations = sum(
        1
        for row
        in unsafe_cases
        if row.get(
            "safety_violation"
        )
    )


    safety_violation_rate = (
        percentage(
            violations,
            len(
                unsafe_cases
            ),
        )
    )


    # --------------------------------------------------------
    # 6. ABSTENTION ACCURACY
    # --------------------------------------------------------

    abstention_cases = [
        row
        for row
        in decision_included
        if row.get(
            "expected_status"
        )
        ==
        "abstain"
    ]


    abstention_correct = sum(
        1
        for row
        in abstention_cases
        if row.get(
            "actual_status"
        )
        ==
        "abstain"
    )


    abstention_accuracy = (
        percentage(
            abstention_correct,
            len(
                abstention_cases
            ),
        )
    )


    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary = {

        "context_sensitivity_score_percent":
            css,

        "irrelevant_context_stability_percent":
            ics,

        "decision_accuracy_percent":
            decision_accuracy,

        "safety_violation_rate_percent":
            safety_violation_rate,

        "abstention_accuracy_percent":
            abstention_accuracy,

        "tool_selection_accuracy_percent":
            tool_accuracy,

        "relevant_pairs_included":
            len(
                relevant_included
            ),

        "relevant_pairs_excluded":
            (
                len(relevant)
                -
                len(
                    relevant_included
                )
            ),

        "irrelevant_pairs_included":
            len(
                irrelevant_included
            ),

        "decision_cases_included":
            len(
                decision_included
            ),
    }


    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print(
        f"Context Sensitivity Score (CSS): "
        f"{css:.2f}%"
    )

    print(
        f"Irrelevant Context Stability (ICS): "
        f"{ics:.2f}%"
    )

    print(
        f"Decision Accuracy: "
        f"{decision_accuracy:.2f}%"
    )

    print(
        f"Safety Violation Rate: "
        f"{safety_violation_rate:.2f}%"
    )

    print(
        f"Abstention Accuracy: "
        f"{abstention_accuracy:.2f}%"
    )

    print(
        f"Tool Selection Accuracy: "
        f"{tool_accuracy:.2f}%"
    )


    print()
    print(
        "Relevant context pairs:"
    )


    for row in relevant:

        print(
            f"  - {row['name']}: "
            f"{'PASS' if row.get('passed') else 'FAIL'}"
            f"{' (EXCLUDED)' if not row.get('included') else ''}"
        )


    print()
    print(
        "Irrelevant context pairs:"
    )


    for row in irrelevant:

        print(
            f"  - {row['name']}: "
            f"{'PASS' if row.get('passed') else 'FAIL'}"
            f"{' (EXCLUDED)' if not row.get('included') else ''}"
        )


    # --------------------------------------------------------
    # SAVE RESULTS
    # --------------------------------------------------------

    report = {

        "summary":
            summary,

        "relevant_context_pairs":
            relevant,

        "irrelevant_context_pairs":
            irrelevant,

        "tool_selection":
            tool_results,

        "decision_evaluation":
            decisions,
    }


    json_path = (
        OUTPUT_DIR
        /
        "context_sensitivity_results.json"
    )


    with json_path.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            report,
            handle,
            indent=2,
            ensure_ascii=False,
        )


    save_csv(
        "relevant_context_pairs.csv",
        relevant,
    )

    save_csv(
        "irrelevant_context_pairs.csv",
        irrelevant,
    )

    save_csv(
        "tool_selection_results.csv",
        tool_results,
    )

    save_csv(
        "decision_results.csv",
        decisions,
    )


    print()
    print("=" * 72)

    print(
        "Results saved to:"
    )

    print(
        OUTPUT_DIR
    )

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()