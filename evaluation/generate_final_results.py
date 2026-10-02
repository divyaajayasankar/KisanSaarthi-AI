# C:\farmer\evaluation\generate_final_results.py

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT / "results" / "evaluation"

FINAL_DIR = RESULTS_DIR / "final"

FINAL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


PHASE14_FILE = (
    RESULTS_DIR
    / "context_sensitivity_results.json"
)

ABLATION_FILE = (
    RESULTS_DIR
    / "ablation_results.json"
)


# ============================================================
# LOAD JSON
# ============================================================

def load_json(path: Path):

    if not path.exists():

        raise FileNotFoundError(
            f"Required result file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(handle)


# ============================================================
# LOAD RESULTS
# ============================================================

phase14 = load_json(
    PHASE14_FILE
)

ablation = load_json(
    ABLATION_FILE
)


summary = phase14[
    "summary"
]

ablation_rows = ablation[
    "results"
]


# ============================================================
# PHASE 14 METRIC TABLE
# ============================================================

phase14_metrics = [

    {
        "metric":
            "Context Sensitivity Score (CSS)",

        "value_percent":
            summary[
                "context_sensitivity_score_percent"
            ],
    },

    {
        "metric":
            "Irrelevant Context Stability (ICS)",

        "value_percent":
            summary[
                "irrelevant_context_stability_percent"
            ],
    },

    {
        "metric":
            "Decision Accuracy",

        "value_percent":
            summary[
                "decision_accuracy_percent"
            ],
    },

    {
        "metric":
            "Safety Violation Rate",

        "value_percent":
            summary[
                "safety_violation_rate_percent"
            ],
    },

    {
        "metric":
            "Abstention Accuracy",

        "value_percent":
            summary[
                "abstention_accuracy_percent"
            ],
    },

    {
        "metric":
            "Tool Selection Accuracy",

        "value_percent":
            summary[
                "tool_selection_accuracy_percent"
            ],
    },
]


# ============================================================
# SAVE PHASE 14 METRICS CSV
# ============================================================

phase14_csv = (
    FINAL_DIR
    / "final_phase14_metrics.csv"
)

with phase14_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "metric",
            "value_percent",
        ],
    )

    writer.writeheader()

    writer.writerows(
        phase14_metrics
    )


# ============================================================
# SAVE ABLATION SUMMARY CSV
# ============================================================

ablation_csv = (
    FINAL_DIR
    / "final_ablation_summary.csv"
)

with ablation_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "configuration",
            "passed_cases",
            "total_cases",
            "context_sensitivity_score_percent",
        ],
    )

    writer.writeheader()

    for row in ablation_rows:

        writer.writerow({

            "configuration":
                row[
                    "configuration"
                ],

            "passed_cases":
                row[
                    "passed_cases"
                ],

            "total_cases":
                row[
                    "total_cases"
                ],

            "context_sensitivity_score_percent":
                row[
                    "context_sensitivity_score_percent"
                ],
        })


# ============================================================
# GRAPH 1 — PHASE 14 METRICS
# ============================================================

metric_names = [
    row["metric"]
    for row
    in phase14_metrics
]

metric_values = [
    row["value_percent"]
    for row
    in phase14_metrics
]


plt.figure(
    figsize=(11, 6)
)

bars = plt.bar(
    metric_names,
    metric_values,
)

plt.ylabel(
    "Percentage (%)"
)

plt.xlabel(
    "Evaluation Metric"
)

plt.title(
    "KisanSaarthi AI — Final Evaluation Metrics"
)

plt.ylim(
    0,
    110,
)

plt.xticks(
    rotation=25,
    ha="right",
)


for bar, value in zip(
    bars,
    metric_values,
):

    plt.text(
        bar.get_x()
        + bar.get_width() / 2,

        value + 1,

        f"{value:.2f}%",

        ha="center",
        va="bottom",
    )


plt.tight_layout()

plt.savefig(
    FINAL_DIR
    / "phase14_metrics.png",

    dpi=300,

    bbox_inches="tight",
)

plt.close()


# ============================================================
# GRAPH 2 — ABLATION CSS
# ============================================================

configuration_names = []

configuration_scores = []


DISPLAY_NAMES = {

    "full_system":
        "Full System",

    "without_phi_context":
        "Without PHI",

    "without_growth_stage":
        "Without Growth Stage",

    "without_treatment_history":
        "Without Treatment History",

    "without_weather":
        "Without Weather",

    "without_field_area":
        "Without Field Area",
}


for row in ablation_rows:

    configuration = row[
        "configuration"
    ]

    configuration_names.append(
        DISPLAY_NAMES.get(
            configuration,
            configuration,
        )
    )

    configuration_scores.append(
        row[
            "context_sensitivity_score_percent"
        ]
    )


plt.figure(
    figsize=(11, 6)
)

bars = plt.bar(
    configuration_names,
    configuration_scores,
)

plt.ylabel(
    "Context Sensitivity Score (%)"
)

plt.xlabel(
    "System Configuration"
)

plt.title(
    "KisanSaarthi AI — Context Ablation Study"
)

plt.ylim(
    0,
    110,
)

plt.xticks(
    rotation=25,
    ha="right",
)


for bar, value in zip(
    bars,
    configuration_scores,
):

    plt.text(
        bar.get_x()
        + bar.get_width() / 2,

        value + 1,

        f"{value:.2f}%",

        ha="center",
        va="bottom",
    )


plt.tight_layout()

plt.savefig(
    FINAL_DIR
    / "ablation_css.png",

    dpi=300,

    bbox_inches="tight",
)

plt.close()


# ============================================================
# CALCULATE ABLATION DROPS
# ============================================================

full_system_score = None

for row in ablation_rows:

    if (
        row["configuration"]
        ==
        "full_system"
    ):

        full_system_score = row[
            "context_sensitivity_score_percent"
        ]

        break


ablation_drop_rows = []


if full_system_score is not None:

    for row in ablation_rows:

        score = row[
            "context_sensitivity_score_percent"
        ]

        drop = round(
            full_system_score
            - score,
            2,
        )

        ablation_drop_rows.append({

            "configuration":
                row[
                    "configuration"
                ],

            "css_percent":
                score,

            "drop_from_full_system_percentage_points":
                drop,
        })


drop_csv = (
    FINAL_DIR
    / "ablation_css_drop.csv"
)


with drop_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "configuration",
            "css_percent",
            "drop_from_full_system_percentage_points",
        ],
    )

    writer.writeheader()

    writer.writerows(
        ablation_drop_rows
    )


# ============================================================
# FINAL JSON SUMMARY
# ============================================================

final_summary = {

    "phase14_metrics":
        phase14_metrics,

    "ablation_results":
        ablation_drop_rows,

    "evaluation_scope": {

        "relevant_context_pairs":
            summary[
                "relevant_pairs_included"
            ],

        "irrelevant_context_pairs":
            summary[
                "irrelevant_pairs_included"
            ],

        "decision_cases":
            summary[
                "decision_cases_included"
            ],
    },
}


with (
    FINAL_DIR
    / "final_results_summary.json"
).open(
    "w",
    encoding="utf-8",
) as handle:

    json.dump(
        final_summary,
        handle,
        indent=2,
    )


# ============================================================
# PRINT
# ============================================================

print()
print("=" * 72)
print(
    "KisanSaarthi AI — Final Results Generated"
)
print("=" * 72)

print()

print(
    "Phase 14 Metrics:"
)

for row in phase14_metrics:

    print(
        f"  {row['metric']}: "
        f"{row['value_percent']:.2f}%"
    )


print()
print(
    "Ablation Study:"
)


for row in ablation_drop_rows:

    print(
        f"  {row['configuration']}: "
        f"CSS={row['css_percent']:.2f}% | "
        f"Drop="
        f"{row['drop_from_full_system_percentage_points']:.2f} pp"
    )


print()
print(
    "Final outputs saved to:"
)

print(
    FINAL_DIR
)

print("=" * 72)