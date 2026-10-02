# C:\farmer\app\services\agent_orchestrator.py

from __future__ import annotations

import re
from typing import Any


# ============================================================
# SUPPORTED CROPS
# ============================================================

SUPPORTED_CROPS = [
    "rice",
    "wheat",
    "maize",
    "tomato",
    "chilli",
    "brinjal",
    "onion",
    "potato",
    "okra",
    "cabbage",
    "groundnut",
    "chickpea",
    "mustard",
    "cotton",
    "banana",
]


# ============================================================
# INTENT KEYWORDS
# ============================================================

ADVISORY_KEYWORDS = {
    "spray",
    "apply",
    "application",
    "pesticide",
    "fungicide",
    "insecticide",
    "dose",
    "dosage",
    "safe to use",
    "can i use",
    "can i spray",
    "should i spray",
    "recommend",
    "harvest",
    "phi",
}


WEATHER_KEYWORDS = {
    "weather",
    "rain",
    "rainfall",
    "wind",
    "temperature",
    "humidity",
    "forecast",
}


SOIL_KEYWORDS = {
    "soil",
    "ph",
    "soil ph",
    "texture",
    "clay",
    "sandy",
    "loam",
    "soil moisture",
}


KNOWLEDGE_KEYWORDS = {
    "how to manage",
    "how can i manage",
    "how to control",
    "control",
    "management",
    "symptom",
    "symptoms",
    "what is",
    "why",
    "disease",
    "pest",
}


TREATMENT_KEYWORDS = {
    "previous spray",
    "last spray",
    "previous treatment",
    "previous application",
    "last application",
    "repeat",
    "rotation",
    "resistance",
    "mode of action",
    "moa",
    "same pesticide",
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value.strip().lower(),
    )


# ============================================================
# KEYWORD MATCHING
# ============================================================

def contains_keyword(
    query: str,
    keywords: set[str],
) -> bool:

    return any(
        keyword in query
        for keyword in keywords
    )


# ============================================================
# CROP INFERENCE
# ============================================================

def infer_crop(
    question: str,
    provided_crop: str | None = None,
) -> str | None:

    if provided_crop:
        return provided_crop.strip()

    query = normalize_text(
        question
    )

    for crop in SUPPORTED_CROPS:

        if re.search(
            rf"\b{re.escape(crop)}\b",
            query,
        ):
            return crop.title()

    return None


# ============================================================
# INTENT INFERENCE
# ============================================================

def infer_intent(
    question: str,
) -> str:

    query = normalize_text(
        question
    )

    if not query:
        return "unknown"

    # --------------------------------------------------------
    # Treatment / resistance is checked first so queries like
    # "Can I repeat the same pesticide?" are routed correctly.
    # --------------------------------------------------------

    if contains_keyword(
        query,
        TREATMENT_KEYWORDS,
    ):
        return "treatment_resistance"

    # --------------------------------------------------------
    # Full spray/advisory decision
    # --------------------------------------------------------

    if contains_keyword(
        query,
        ADVISORY_KEYWORDS,
    ):
        return "advisory"

    # --------------------------------------------------------
    # Weather specialist
    # --------------------------------------------------------

    if contains_keyword(
        query,
        WEATHER_KEYWORDS,
    ):
        return "weather"

    # --------------------------------------------------------
    # Soil specialist
    # --------------------------------------------------------

    if contains_keyword(
        query,
        SOIL_KEYWORDS,
    ):
        return "soil"

    # --------------------------------------------------------
    # Knowledge / RAG
    # --------------------------------------------------------

    if contains_keyword(
        query,
        KNOWLEDGE_KEYWORDS,
    ):
        return "knowledge"

    # Unknown natural-language crop questions
    # fall back to verified knowledge retrieval.
    return "knowledge"


# ============================================================
# TOOL SELECTION
# ============================================================

def select_tools(
    intent: str,
) -> list[str]:

    tool_map = {

        "advisory": [
            "registry",
            "dose_phi",
            "growth_stage",
            "treatment_history",
            "resistance",
            "weather",
            "soil",
            "verified_rag",
        ],

        "weather": [
            "weather",
        ],

        "soil": [
            "soil",
        ],

        "knowledge": [
            "verified_rag",
            "registry",
        ],

        "treatment_resistance": [
            "registry",
            "treatment_history",
            "resistance",
        ],

        "unknown": [
            "verified_rag",
        ],
    }

    return tool_map.get(
        intent,
        ["verified_rag"],
    )


# ============================================================
# MISSING CONTEXT DETECTION
# ============================================================

def determine_missing_context(
    intent: str,
    context: dict[str, Any],
) -> list[str]:

    missing: list[str] = []

    crop = context.get(
        "crop"
    )

    pest = context.get(
        "pest"
    )


    # ========================================================
    # CROP REQUIREMENT
    # ========================================================

    if intent in {
        "advisory",
        "knowledge",
        "treatment_resistance",
    }:

        if not crop:
            missing.append(
                "crop"
            )


    # ========================================================
    # PEST REQUIREMENT
    # ========================================================

    if intent in {
        "advisory",
        "treatment_resistance",
    }:

        if not pest:
            missing.append(
                "pest"
            )


    # ========================================================
    # FULL ADVISORY CONTEXT
    # ========================================================

    if intent == "advisory":

        required_fields = [
            "field_area",
            "area_unit",
            "expected_harvest_days",
            "growth_stage",
            "previous_application_count",
        ]

        for field in required_fields:

            if context.get(field) is None:

                missing.append(
                    field
                )


        # ----------------------------------------------------
        # IMPORTANT:
        # Existing weather_service.py uses State + District.
        #
        # Latitude / longitude are NOT a replacement here.
        # They are used separately by the soil specialist.
        # ----------------------------------------------------

        if not context.get(
            "state"
        ):
            missing.append(
                "state"
            )


        if not context.get(
            "district"
        ):
            missing.append(
                "district"
            )


    # ========================================================
    # WEATHER SPECIALIST CONTEXT
    # ========================================================

    elif intent == "weather":

        # Existing weather service requires
        # both State and District.

        if not context.get(
            "state"
        ):
            missing.append(
                "state"
            )


        if not context.get(
            "district"
        ):
            missing.append(
                "district"
            )


    # ========================================================
    # SOIL SPECIALIST CONTEXT
    # ========================================================

    elif intent == "soil":

        latitude = context.get(
            "latitude"
        )

        longitude = context.get(
            "longitude"
        )


        if (
            latitude is None
            or longitude is None
        ):
            missing.append(
                "latitude_longitude"
            )


    return missing


# ============================================================
# HUMAN-READABLE AGENT PLAN
# ============================================================

def build_plan_steps(
    selected_tools: list[str],
) -> list[str]:

    descriptions = {

        "registry":
            "Check verified crop-pest registry evidence.",

        "dose_phi":
            "Validate registered dose and harvest safety.",

        "growth_stage":
            "Check whether the crop growth stage is suitable.",

        "treatment_history":
            "Evaluate previous treatment count and repeat interval.",

        "resistance":
            "Check mode-of-action and resistance rotation context.",

        "weather":
            "Evaluate local weather suitability.",

        "soil":
            "Evaluate soil context and crop-soil suitability.",

        "verified_rag":
            "Retrieve supporting evidence from the verified knowledge base.",
    }


    return [

        descriptions[tool]

        for tool in selected_tools

        if tool in descriptions
    ]


# ============================================================
# MAIN AGENT PLANNER
# ============================================================

def plan_farmer_query(
    question: str,
    *,
    crop: str | None = None,
    pest: str | None = None,
    field_area: float | None = None,
    area_unit: str | None = None,
    expected_harvest_days: int | None = None,
    growth_stage: str | None = None,
    previous_application_count: int | None = None,
    days_since_last_application: int | None = None,
    state: str | None = None,
    district: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:

    # ========================================================
    # 1. UNDERSTAND CROP
    # ========================================================

    inferred_crop = infer_crop(
        question,
        crop,
    )


    # ========================================================
    # 2. UNDERSTAND FARMER INTENT
    # ========================================================

    intent = infer_intent(
        question
    )


    # ========================================================
    # 3. BUILD AVAILABLE FARMER CONTEXT
    # ========================================================

    context = {

        "crop":
            inferred_crop,

        "pest":
            pest,

        "field_area":
            field_area,

        "area_unit":
            area_unit,

        "expected_harvest_days":
            expected_harvest_days,

        "growth_stage":
            growth_stage,

        "previous_application_count":
            previous_application_count,

        "days_since_last_application":
            days_since_last_application,

        "state":
            state,

        "district":
            district,

        "latitude":
            latitude,

        "longitude":
            longitude,
    }


    # ========================================================
    # 4. SELECT REQUIRED SPECIALIST TOOLS
    # ========================================================

    selected_tools = select_tools(
        intent
    )


    # ========================================================
    # 5. CHECK WHETHER REQUIRED CONTEXT IS AVAILABLE
    # ========================================================

    missing_context = (
        determine_missing_context(
            intent,
            context,
        )
    )


    # ========================================================
    # 6. RETURN AGENT PLAN
    # ========================================================

    return {

        "question":
            question,

        "intent":
            intent,

        "entities": {

            "crop":
                inferred_crop,

            "pest":
                pest,
        },

        "selected_tools":
            selected_tools,

        "missing_context":
            missing_context,

        "ready_to_execute":
            len(
                missing_context
            ) == 0,

        "plan":
            build_plan_steps(
                selected_tools
            ),
    }