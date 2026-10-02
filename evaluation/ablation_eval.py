# C:\farmer\evaluation\ablation_eval.py

from __future__ import annotations

import csv
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch


# ============================================================
# PROJECT PATH
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============================================================
# OUTPUT
# ============================================================

OUTPUT_DIR = ROOT / "results" / "evaluation"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# REPRODUCIBLE WEATHER
# ============================================================

def make_weather(
    mode: str = "safe",
) -> dict[str, Any]:

    if mode == "high_wind":

        wind = 7.5
        rain = 0.0
        rain_probability = 0.10

    else:

        wind = 2.0
        rain = 0.0
        rain_probability = 0.10


    return {

        "weather": {

            "forecast_window_hours": 24,

            "rain_total_mm": rain,

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
            "MockWeather-Ablation",
    }


# ============================================================
# RUN ADVISORY
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
# BASE CONTEXT
# ============================================================

RICE_BASE = {

    "farmer_id": None,

    "crop": "Rice",

    "pest":
        "Blast; Sheath blight",

    "field_area": 0.5,

    "area_unit": "hectare",

    "expected_harvest_days": 40,

    "growth_stage":
        "vegetative",

    "previous_application_count": 0,

    "days_since_last_application":
        None,

    "state":
        "Tamil Nadu",

    "district":
        "Coimbatore",

    "latitude":
        None,

    "longitude":
        None,
}


BANANA_BASE = {

    "farmer_id": None,

    "crop": "Banana",

    "pest": "Sigatoka",

    "field_area": 0.5,

    "area_unit": "hectare",

    "expected_harvest_days": 30,

    "growth_stage":
        "vegetative",

    "previous_application_count": 1,

    "days_since_last_application": 20,

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
# HELPER
# ============================================================

def changed(
    result_a: dict[str, Any],
    result_b: dict[str, Any],
    fields: list[str],
) -> bool:

    return any(
        result_a.get(field)
        != result_b.get(field)
        for field in fields
    )


def percent(
    numerator: int,
    denominator: int,
) -> float:

    if denominator == 0:
        return 0.0

    return round(
        (
            numerator
            / denominator
        )
        * 100,
        2,
    )


# ============================================================
# ABLATION TRANSFORMATIONS
#
# These suppress one decision-relevant context dimension.
# ============================================================

def apply_ablation(
    payload: dict[str, Any],
    ablation: str,
) -> dict[str, Any]:

    output = deepcopy(
        payload
    )


    # --------------------------------------------------------
    # PHI CONTEXT REMOVED
    #
    # Replace actual harvest horizon with a fixed safe horizon.
    # --------------------------------------------------------

    if ablation == "without_phi_context":

        output[
            "expected_harvest_days"
        ] = 120


    # --------------------------------------------------------
    # GROWTH-STAGE CONTEXT REMOVED
    #
    # Force all cases to the same stage.
    # --------------------------------------------------------

    elif ablation == "without_growth_stage":

        output[
            "growth_stage"
        ] = "vegetative"


    # --------------------------------------------------------
    # TREATMENT HISTORY REMOVED
    # --------------------------------------------------------

    elif ablation == "without_treatment_history":

        output[
            "previous_application_count"
        ] = 0

        output[
            "days_since_last_application"
        ] = None


    # --------------------------------------------------------
    # FIELD-AREA PERSONALIZATION REMOVED
    #
    # Every farmer is treated as having 1 hectare.
    # --------------------------------------------------------

    elif ablation == "without_field_area":

        output[
            "field_area"
        ] = 1.0

        output[
            "area_unit"
        ] = "hectare"


    return output


# ============================================================
# PHI SENSITIVITY CASE
# ============================================================

def phi_case(
    ablation: str,
):

    first = deepcopy(
        RICE_BASE
    )

    second = deepcopy(
        RICE_BASE
    )

    first[
        "expected_harvest_days"
    ] = 40

    second[
        "expected_harvest_days"
    ] = 5


    first = apply_ablation(
        first,
        ablation,
    )

    second = apply_ablation(
        second,
        ablation,
    )


    result_a = run_advisory(
        first,
        weather_mode="safe",
    )

    result_b = run_advisory(
        second,
        weather_mode="safe",
    )


    return changed(
        result_a,
        result_b,
        [
            "status",
            "active_ingredient",
        ],
    )


# ============================================================
# GROWTH-STAGE CASE
# ============================================================

def growth_case(
    ablation: str,
):

    first = deepcopy(
        RICE_BASE
    )

    second = deepcopy(
        RICE_BASE
    )

    first[
        "growth_stage"
    ] = "vegetative"

    second[
        "growth_stage"
    ] = "pre_harvest"


    first = apply_ablation(
        first,
        ablation,
    )

    second = apply_ablation(
        second,
        ablation,
    )


    result_a = run_advisory(
        first,
        weather_mode="safe",
    )

    result_b = run_advisory(
        second,
        weather_mode="safe",
    )


    return changed(
        result_a,
        result_b,
        [
            "status",
            "active_ingredient",
        ],
    )


# ============================================================
# TREATMENT COUNT CASE
# ============================================================

def treatment_case(
    ablation: str,
):

    first = deepcopy(
        RICE_BASE
    )

    second = deepcopy(
        RICE_BASE
    )

    first[
        "previous_application_count"
    ] = 2

    second[
        "previous_application_count"
    ] = 3


    first = apply_ablation(
        first,
        ablation,
    )

    second = apply_ablation(
        second,
        ablation,
    )


    result_a = run_advisory(
        first,
        weather_mode="safe",
    )

    result_b = run_advisory(
        second,
        weather_mode="safe",
    )


    return changed(
        result_a,
        result_b,
        [
            "status",
            "active_ingredient",
        ],
    )


# ============================================================
# REPEAT INTERVAL CASE
# ============================================================

def repeat_interval_case(
    ablation: str,
):

    first = deepcopy(
        BANANA_BASE
    )

    second = deepcopy(
        BANANA_BASE
    )

    first[
        "days_since_last_application"
    ] = 20

    second[
        "days_since_last_application"
    ] = 5


    first = apply_ablation(
        first,
        ablation,
    )

    second = apply_ablation(
        second,
        ablation,
    )


    result_a = run_advisory(
        first,
        weather_mode="safe",
    )

    result_b = run_advisory(
        second,
        weather_mode="safe",
    )


    return changed(
        result_a,
        result_b,
        [
            "status",
            "active_ingredient",
        ],
    )


# ============================================================
# WEATHER CASE
# ============================================================

def weather_case(
    ablation: str,
):

    payload = deepcopy(
        RICE_BASE
    )

    payload = apply_ablation(
        payload,
        ablation,
    )


    # --------------------------------------------------------
    # Full system:
    # safe vs high-wind weather.
    #
    # Weather ablation:
    # both runs receive identical safe weather.
    # --------------------------------------------------------

    if ablation == "without_weather":

        result_a = run_advisory(
            payload,
            weather_mode="safe",
        )

        result_b = run_advisory(
            payload,
            weather_mode="safe",
        )

    else:

        result_a = run_advisory(
            payload,
            weather_mode="safe",
        )

        result_b = run_advisory(
            payload,
            weather_mode="high_wind",
        )


    return changed(
        result_a,
        result_b,
        [
            "status",
            "active_ingredient",
        ],
    )


# ============================================================
# FIELD AREA CASE
# ============================================================

def area_case(
    ablation: str,
):

    first = deepcopy(
        RICE_BASE
    )

    second = deepcopy(
        RICE_BASE
    )

    first[
        "field_area"
    ] = 0.5

    second[
        "field_area"
    ] = 1.0


    first = apply_ablation(
        first,
        ablation,
    )

    second = apply_ablation(
        second,
        ablation,
    )


    result_a = run_advisory(
        first,
        weather_mode="safe",
    )

    result_b = run_advisory(
        second,
        weather_mode="safe",
    )


    return changed(
        result_a,
        result_b,
        [
            "scaled_dose_min",
            "scaled_dose_max",
        ],
    )


# ============================================================
# RUN ONE CONFIGURATION
# ============================================================

def evaluate_configuration(
    name: str,
) -> dict[str, Any]:

    cases = {

        "phi":
            phi_case(name),

        "growth_stage":
            growth_case(name),

        "treatment_count":
            treatment_case(name),

        "repeat_interval":
            repeat_interval_case(name),

        "weather":
            weather_case(name),

        "field_area":
            area_case(name),
    }


    passed = sum(
        1
        for value
        in cases.values()
        if value
    )


    css = percent(
        passed,
        len(cases),
    )


    return {

        "configuration":
            name,

        "phi_sensitive":
            cases["phi"],

        "growth_stage_sensitive":
            cases[
                "growth_stage"
            ],

        "treatment_count_sensitive":
            cases[
                "treatment_count"
            ],

        "repeat_interval_sensitive":
            cases[
                "repeat_interval"
            ],

        "weather_sensitive":
            cases["weather"],

        "field_area_sensitive":
            cases[
                "field_area"
            ],

        "passed_cases":
            passed,

        "total_cases":
            len(cases),

        "context_sensitivity_score_percent":
            css,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    configurations = [

        "full_system",

        "without_phi_context",

        "without_growth_stage",

        "without_treatment_history",

        "without_weather",

        "without_field_area",
    ]


    rows = []


    print()
    print("=" * 76)
    print(
        "KisanSaarthi AI — Context Ablation Study"
    )
    print("=" * 76)
    print()


    for configuration in configurations:

        result = evaluate_configuration(
            configuration
        )

        rows.append(
            result
        )


        print(
            f"{configuration:<30}"
            f"CSS = "
            f"{result['context_sensitivity_score_percent']:.2f}% "
            f"({result['passed_cases']}/"
            f"{result['total_cases']})"
        )


    # ========================================================
    # SAVE JSON
    # ========================================================

    json_path = (
        OUTPUT_DIR
        / "ablation_results.json"
    )


    with json_path.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            {
                "study_type":
                    "input-context ablation",

                "description": (
                    "Each ablation suppresses one "
                    "decision-relevant farmer context "
                    "dimension while keeping the underlying "
                    "advisory engine unchanged."
                ),

                "results":
                    rows,
            },
            handle,
            indent=2,
        )


    # ========================================================
    # SAVE CSV
    # ========================================================

    csv_path = (
        OUTPUT_DIR
        / "ablation_results.csv"
    )


    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


    print()
    print(
        "Results saved to:"
    )

    print(
        OUTPUT_DIR
    )

    print()
    print("=" * 76)


if __name__ == "__main__":
    main()