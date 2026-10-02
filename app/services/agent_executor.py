# C:\farmer\app\services\agent_executor.py

from __future__ import annotations

from typing import Any

from app.services.weather_service import (
    WeatherServiceError,
    get_location_weather,
)

from app.services.weather_rules import (
    evaluate_weather_safety,
)

from app.services.soil_service import (
    SoilServiceError,
)

from app.services.soilgrids_rootzone import (
    get_root_zone_soil_context,
)

from app.services.rag_service import (
    retrieve_verified_evidence,
)


# ============================================================
# WEATHER SPECIALIST
# ============================================================

def execute_weather_specialist(
    *,
    state: str | None,
    district: str | None,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # REQUIRED LOCATION CONTEXT
    # --------------------------------------------------------

    missing_context: list[str] = []

    if not state:
        missing_context.append("state")

    if not district:
        missing_context.append("district")

    if missing_context:

        return {
            "status": "needs_context",
            "tool": "weather",
            "missing_context": missing_context,
            "result": None,
        }

    # --------------------------------------------------------
    # FETCH VERIFIED WEATHER
    # --------------------------------------------------------

    try:

        weather_data = get_location_weather(
            district=district,
            state=state,
        )

        weather = weather_data.get(
            "weather"
        )

        if weather is None:

            return {
                "status": "unavailable",
                "tool": "weather",
                "explanation": (
                    "Weather data was returned without "
                    "a usable weather observation."
                ),
                "result": None,
            }

        # ----------------------------------------------------
        # APPLY EXISTING WEATHER SAFETY RULES
        # ----------------------------------------------------

        weather_result = (
            evaluate_weather_safety(
                weather
            )
        )

        return {
            "status": "completed",
            "tool": "weather",

            "location": {
                "state": state,
                "district": district,
            },

            "weather": weather,

            "source": weather_data.get(
                "source"
            ),

            "spray_safety": {
                "status":
                    weather_result.status,

                "explanation":
                    weather_result.explanation,

                "fired_rules":
                    weather_result.fired_rules,
            },
        }

    except WeatherServiceError as exc:

        return {
            "status": "unavailable",
            "tool": "weather",
            "explanation": (
                "Current weather evidence could "
                "not be verified."
            ),
            "error": str(exc),
            "result": None,
        }

    except Exception as exc:

        return {
            "status": "unavailable",
            "tool": "weather",
            "explanation": (
                "Weather specialist execution failed."
            ),
            "error": str(exc),
            "result": None,
        }


# ============================================================
# SOIL SPECIALIST
# ============================================================

def execute_soil_specialist(
    *,
    latitude: float | None,
    longitude: float | None,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # REQUIRED COORDINATES
    # --------------------------------------------------------

    if (
        latitude is None
        or longitude is None
    ):

        return {
            "status": "needs_context",
            "tool": "soil",
            "missing_context": [
                "latitude_longitude"
            ],
            "result": None,
        }

    # --------------------------------------------------------
    # VALIDATE COORDINATE RANGE
    # --------------------------------------------------------

    if not (
        -90 <= latitude <= 90
    ):

        return {
            "status": "invalid_context",
            "tool": "soil",
            "explanation": (
                "Latitude must be between "
                "-90 and 90."
            ),
            "result": None,
        }

    if not (
        -180 <= longitude <= 180
    ):

        return {
            "status": "invalid_context",
            "tool": "soil",
            "explanation": (
                "Longitude must be between "
                "-180 and 180."
            ),
            "result": None,
        }

    # --------------------------------------------------------
    # FETCH ROOT-ZONE SOIL CONTEXT
    # --------------------------------------------------------

    try:

        soil_data = (
            get_root_zone_soil_context(
                latitude=latitude,
                longitude=longitude,
            )
        )

        return {
            "status": "completed",
            "tool": "soil",

            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
            },

            "soil": {
                "coordinates":
                    soil_data.get(
                        "coordinates"
                    ),

                "root_zone_depth":
                    soil_data.get(
                        "root_zone_depth"
                    ),

                "root_zone":
                    soil_data.get(
                        "root_zone"
                    ),

                "aggregation":
                    soil_data.get(
                        "aggregation"
                    ),
            },

            "source":
                soil_data.get(
                    "source"
                ),
        }

    except SoilServiceError as exc:

        return {
            "status": "unavailable",
            "tool": "soil",
            "explanation": (
                "Current soil evidence could "
                "not be verified."
            ),
            "error": str(exc),
            "result": None,
        }

    except Exception as exc:

        return {
            "status": "unavailable",
            "tool": "soil",
            "explanation": (
                "Soil specialist execution failed."
            ),
            "error": str(exc),
            "result": None,
        }


# ============================================================
# VERIFIED KNOWLEDGE / RAG SPECIALIST
# ============================================================

def execute_knowledge_specialist(
    *,
    question: str,
    crop: str | None,
    top_k: int = 3,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # VALIDATE QUESTION
    # --------------------------------------------------------

    if not question or not question.strip():

        return {
            "status": "needs_context",
            "tool": "verified_rag",
            "missing_context": [
                "question"
            ],
            "result": None,
        }

    # --------------------------------------------------------
    # CROP IS REQUIRED FOR CROP-SPECIFIC VERIFIED RETRIEVAL
    # --------------------------------------------------------

    if not crop or not crop.strip():

        return {
            "status": "needs_context",
            "tool": "verified_rag",
            "missing_context": [
                "crop"
            ],
            "result": None,
        }

    # --------------------------------------------------------
    # VALIDATE TOP-K
    # --------------------------------------------------------

    if top_k <= 0:

        top_k = 3

    # --------------------------------------------------------
    # RETRIEVE VERIFIED AGRICULTURAL EVIDENCE
    # --------------------------------------------------------

    try:

        rag_result = (
            retrieve_verified_evidence(
                query=question.strip(),
                crop=crop.strip(),
                top_k=top_k,
            )
        )

        return {
            "status": "completed",
            "tool": "verified_rag",
            "crop": crop.strip(),
            "query": question.strip(),
            "result": rag_result,
        }

    except Exception as exc:

        return {
            "status": "unavailable",
            "tool": "verified_rag",
            "explanation": (
                "Verified agricultural knowledge "
                "retrieval failed."
            ),
            "error": str(exc),
            "result": None,
        }


# ============================================================
# MAIN SPECIALIST EXECUTOR
# ============================================================

def execute_specialist(
    *,
    intent: str,
    question: str,
    crop: str | None = None,
    state: str | None = None,
    district: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # WEATHER
    # --------------------------------------------------------

    if intent == "weather":

        return execute_weather_specialist(
            state=state,
            district=district,
        )

    # --------------------------------------------------------
    # SOIL
    # --------------------------------------------------------

    if intent == "soil":

        return execute_soil_specialist(
            latitude=latitude,
            longitude=longitude,
        )

    # --------------------------------------------------------
    # VERIFIED KNOWLEDGE / RAG
    # --------------------------------------------------------

    if intent == "knowledge":

        return execute_knowledge_specialist(
            question=question,
            crop=crop,
        )

    # --------------------------------------------------------
    # INTENT NOT CONNECTED HERE
    # --------------------------------------------------------

    return {
        "status": "unsupported_intent",
        "tool": None,
        "intent": intent,
        "explanation": (
            "No specialist executor is configured "
            "for this intent."
        ),
        "result": None,
    }