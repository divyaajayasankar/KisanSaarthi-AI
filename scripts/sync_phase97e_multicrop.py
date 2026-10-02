from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

REGISTRY_FILE = (
    PROJECT_ROOT
    / "data"
    / "registry"
    / "crop_registry_15.csv"
)

RESISTANCE_FILE = (
    PROJECT_ROOT
    / "data"
    / "resistance"
    / "resistance_rules.csv"
)

TREATMENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "treatment_history"
    / "treatment_history_rules.csv"
)

GROWTH_FILE = (
    PROJECT_ROOT
    / "data"
    / "growth_stage"
    / "growth_stage_rules.csv"
)

RAG_FILE = (
    PROJECT_ROOT
    / "data"
    / "rag"
    / "knowledge_base.json"
)

COVERAGE_FILE = (
    PROJECT_ROOT
    / "data"
    / "coverage"
    / "crop_coverage.json"
)


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def load_csv(path):
    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        return list(
            csv.DictReader(file)
        )


def write_csv(
    path,
    fieldnames,
    rows,
):
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# LOAD 15-CROP REGISTRY
# ============================================================

registry_rows = load_csv(
    REGISTRY_FILE
)

print(
    f"Registry seed rows: "
    f"{len(registry_rows)}"
)


# ============================================================
# 1. RESISTANCE RULES
# ============================================================

resistance_rows = load_csv(
    RESISTANCE_FILE
)

resistance_fields = [
    "crop",
    "pest",
    "active_ingredient",
    "framework",
    "moa_group",
    "moa_name",
    "resistance_risk",
    "rotation_recommended",
    "verified",
    "source_name",
    "source_url",
    "notes",
]


MOA_INFO = {

    (
        "IRAC",
        "28",
    ): {
        "name":
            "Ryanodine receptor modulators (Diamides)",

        "risk":
            "managed",

        "source":
            "IRAC Mode of Action",

        "url":
            "https://irac-online.org/mode-of-action/",
    },

    (
        "IRAC",
        "4A",
    ): {
        "name":
            "Neonicotinoids",

        "risk":
            "managed",

        "source":
            "IRAC Mode of Action",

        "url":
            "https://irac-online.org/mode-of-action/",
    },

    (
        "IRAC",
        "2B",
    ): {
        "name":
            "Phenylpyrazoles (Fiproles)",

        "risk":
            "managed",

        "source":
            "IRAC Mode of Action",

        "url":
            "https://irac-online.org/mode-of-action/",
    },

    (
        "FRAC",
        "11",
    ): {
        "name":
            "QoI fungicides",

        "risk":
            "high",

        "source":
            "FRAC QoI Fungicides",

        "url":
            (
                "https://www.frac.info/"
                "frac-teams/working-groups/"
                "qi-fungicides/qol-fungicides/"
            ),
    },
}


def resistance_exists(
    crop,
    pest,
    ingredient,
):
    for row in resistance_rows:

        if (
            clean(row.get("crop")).lower()
            == crop.lower()

            and
            clean(row.get("pest")).lower()
            == pest.lower()

            and
            clean(
                row.get(
                    "active_ingredient"
                )
            ).lower()
            == ingredient.lower()
        ):
            return True

    return False


new_resistance = 0


for row in registry_rows:

    crop = clean(
        row.get("crop")
    )

    pest = clean(
        row.get("pest")
    )

    active = clean(
        row.get(
            "active_ingredient"
        )
    )

    framework = clean(
        row.get(
            "moa_system"
        )
    ).upper()

    group_text = clean(
        row.get(
            "moa_group"
        )
    )


    # --------------------------------------------------------
    # Split combination products.
    #
    # Example:
    # Thiamethoxam + Fipronil
    # 4A + 2B
    # --------------------------------------------------------

    ingredients = [
        x.strip()
        for x in active.split("+")
        if x.strip()
    ]

    groups = [
        x.strip()
        for x in group_text.split("+")
        if x.strip()
    ]


    if len(ingredients) != len(groups):

        if (
            len(ingredients) == 1
            and
            len(groups) == 1
        ):
            pass

        else:
            print(
                "Resistance mapping skipped: "
                f"{crop} | {active}"
            )

            continue


    for ingredient, group in zip(
        ingredients,
        groups,
    ):

        info = MOA_INFO.get(
            (
                framework,
                group,
            )
        )

        if not info:
            continue


        if resistance_exists(
            crop,
            pest,
            ingredient,
        ):
            continue


        resistance_rows.append(
            {
                "crop":
                    crop,

                "pest":
                    pest,

                "active_ingredient":
                    ingredient,

                "framework":
                    framework,

                "moa_group":
                    group,

                "moa_name":
                    info["name"],

                "resistance_risk":
                    info["risk"],

                "rotation_recommended":
                    "True",

                "verified":
                    "True",

                "source_name":
                    info["source"],

                "source_url":
                    info["url"],

                "notes": (
                    f"{ingredient} is classified "
                    f"in {framework} group {group}. "
                    "KisanSaarthi uses the MoA group "
                    "for resistance-rotation guidance."
                ),
            }
        )

        new_resistance += 1


write_csv(
    RESISTANCE_FILE,
    resistance_fields,
    resistance_rows,
)


# ============================================================
# 2. TREATMENT HISTORY
# ============================================================

treatment_rows = load_csv(
    TREATMENT_FILE
)

treatment_fields = [
    "crop",
    "pest",
    "active_ingredient",
    "max_applications",
    "min_interval_days",
    "history_scope",
    "application_stage",
    "verified",
    "source_document",
    "source_page",
    "source_url",
    "notes",
]


def treatment_exists(
    crop,
    pest,
    ingredient,
):
    for row in treatment_rows:

        if (
            clean(row.get("crop")).lower()
            == crop.lower()

            and
            clean(row.get("pest")).lower()
            == pest.lower()

            and
            clean(
                row.get(
                    "active_ingredient"
                )
            ).lower()
            == ingredient.lower()
        ):
            return True

    return False


new_treatment = 0


for row in registry_rows:

    crop = clean(
        row.get("crop")
    )

    pest = clean(
        row.get("pest")
    )

    ingredient = clean(
        row.get(
            "active_ingredient"
        )
    )

    max_applications = clean(
        row.get(
            "max_applications"
        )
    )

    min_interval = clean(
        row.get(
            "min_interval_days"
        )
    )


    # Never invent frequency.
    if (
        not max_applications
        and
        not min_interval
    ):
        continue


    if treatment_exists(
        crop,
        pest,
        ingredient,
    ):
        continue


    stage = clean(
        row.get(
            "allowed_growth_stages"
        )
    )


    treatment_rows.append(
        {
            "crop":
                crop,

            "pest":
                pest,

            "active_ingredient":
                ingredient,

            "max_applications":
                max_applications,

            "min_interval_days":
                min_interval,

            "history_scope":
                "crop_cycle",

            "application_stage":
                stage,

            "verified":
                "true",

            "source_document":
                clean(
                    row.get(
                        "source_name"
                    )
                ),

            # No exact page was encoded in
            # crop_registry_15.csv.
            "source_page":
                "0",

            "source_url":
                clean(
                    row.get(
                        "source_url"
                    )
                ),

            "notes": (
                "Imported only because the verified "
                "seed record contains an explicit "
                "application-frequency or interval rule. "
                "No missing frequency was inferred."
            ),
        }
    )

    new_treatment += 1


write_csv(
    TREATMENT_FILE,
    treatment_fields,
    treatment_rows,
)


# ============================================================
# 3. RAG KNOWLEDGE
# ============================================================

with RAG_FILE.open(
    "r",
    encoding="utf-8-sig",
) as file:

    rag_records = json.load(
        file
    )


existing_rag_ids = {
    clean(
        item.get("id")
    )
    for item in rag_records
}


def slug(value):
    return (
        value.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(";", "")
        .replace("+", "plus")
        .replace("-", "_")
    )


new_rag = 0


for row in registry_rows:

    crop = clean(
        row.get("crop")
    )

    pest_text = clean(
        row.get("pest")
    )

    active = clean(
        row.get(
            "active_ingredient"
        )
    )

    source_name = clean(
        row.get(
            "source_name"
        )
    )

    source_url = clean(
        row.get(
            "source_url"
        )
    )


    topics = [
        topic.strip()
        for topic in pest_text.split(";")
        if topic.strip()
    ]


    for topic in topics:

        record_id = (
            f"{slug(crop)}_"
            f"{slug(topic)}_"
            f"registry_001"
        )


        if record_id in existing_rag_ids:
            continue


        rag_records.append(
            {
                "id":
                    record_id,

                "crop":
                    crop,

                "topic":
                    topic,

                "category":
                    "verified_registry_evidence",

                "text": (
                    f"The verified official pesticide "
                    f"source lists {active} for "
                    f"{crop} against {topic}. "
                    "KisanSaarthi uses the structured "
                    "registry separately for dose, PHI "
                    "and other safety decisions and does "
                    "not infer missing label information."
                ),

                "source":
                    source_name,

                "source_type":
                    "PPQS/CIB&RC",

                "source_url":
                    source_url,

                "verified":
                    True,
            }
        )

        existing_rag_ids.add(
            record_id
        )

        new_rag += 1


with RAG_FILE.open(
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        rag_records,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# 4. REBUILD FINAL 15-CROP COVERAGE FILE
# ============================================================

growth_rows = load_csv(
    GROWTH_FILE
)


growth_crops = {
    clean(row.get("crop")).lower()
    for row in growth_rows
    if clean(
        row.get("verified")
    ).lower()
    == "true"
}


history_crops = {
    clean(row.get("crop")).lower()
    for row in treatment_rows
    if clean(
        row.get("verified")
    ).lower()
    == "true"
}


resistance_crops = {
    clean(row.get("crop")).lower()
    for row in resistance_rows
    if clean(
        row.get("verified")
    ).lower()
    == "true"
}


rag_crops = {
    clean(
        item.get("crop")
    ).lower()
    for item in rag_records
    if item.get("verified") is True
}


coverage = []


for row in registry_rows:

    crop = clean(
        row.get("crop")
    )

    crop_key = crop.lower()

    phi_required = (
        clean(
            row.get(
                "phi_required"
            )
        ).lower()
        == "true"
    )

    phi_available = bool(
        clean(
            row.get(
                "phi_days"
            )
        )
    )


    coverage_row = {
        "crop":
            crop,

        "status":
            "partial_support",

        "registry":
            True,

        "phi":
            (
                phi_available
                if phi_required
                else False
            ),

        "growth_stage":
            crop_key
            in growth_crops,

        "treatment_history":
            crop_key
            in history_crops,

        "resistance":
            crop_key
            in resistance_crops,

        "weather":
            True,

        "soil":
            True,

        "rag":
            crop_key
            in rag_crops,
    }


    # Complete support is only claimed when all
    # currently required layers are available.
    required = [
        coverage_row["registry"],
        coverage_row["phi"],
        coverage_row["growth_stage"],
        coverage_row[
            "treatment_history"
        ],
        coverage_row["resistance"],
        coverage_row["weather"],
        coverage_row["soil"],
        coverage_row["rag"],
    ]


    if all(required):

        coverage_row[
            "status"
        ] = "supported"


    # Banana remains pending until explicit
    # PHI-not-applicable handling exists in
    # RegistryEntry / constraint engine.
    if crop.lower() == "banana":

        coverage_row[
            "status"
        ] = "pending_phi_na_support"


    coverage.append(
        coverage_row
    )


with COVERAGE_FILE.open(
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        coverage,
        file,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 65)
print("PHASE 9.7E MULTICROP SYNCHRONIZATION")
print("=" * 65)

print(
    f"Resistance rules added : "
    f"{new_resistance}"
)

print(
    f"Treatment rules added  : "
    f"{new_treatment}"
)

print(
    f"RAG records added      : "
    f"{new_rag}"
)

print()

for row in coverage:

    print(
        f"{row['crop']:<15} "
        f"{row['status']:<25} "
        f"G={row['growth_stage']} "
        f"H={row['treatment_history']} "
        f"R={row['resistance']} "
        f"RAG={row['rag']}"
    )

print("=" * 65)