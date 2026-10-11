from typing import Any
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
