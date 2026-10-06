# C:\farmer\tests\test_agent_orchestrator.py

from app.services.agent_orchestrator import (
    infer_crop,
    infer_intent,
    plan_farmer_query,
    select_tools,
)


def test_infer_crop_from_question():

    crop = infer_crop(
        "How can I manage blast in my rice crop?"
    )

    assert crop == "Rice"


def test_advisory_intent():

    intent = infer_intent(
        "Can I spray for banana Sigatoka today?"
    )

    assert intent == "advisory"


def test_weather_intent():

    intent = infer_intent(
        "Will it rain today?"
    )

    assert intent == "weather"


def test_soil_intent():

    intent = infer_intent(
        "What is the soil pH of my field?"
    )

    assert intent == "soil"


def test_knowledge_intent():

    intent = infer_intent(
        "How can I manage rice blast?"
    )

    assert intent == "knowledge"


def test_advisory_selects_full_tool_chain():

    tools = select_tools(
        "advisory"
    )

    assert "registry" in tools
    assert "dose_phi" in tools
    assert "growth_stage" in tools
    assert "treatment_history" in tools
    assert "resistance" in tools
    assert "weather" in tools
    assert "soil" in tools
    assert "verified_rag" in tools


def test_weather_selects_only_weather():

    tools = select_tools(
        "weather"
    )

    assert tools == [
        "weather"
    ]


def test_missing_context_detected():

    result = plan_farmer_query(
        "Can I spray for rice blast today?",
        crop="Rice",
        pest="Blast",
    )

    assert result["intent"] == "advisory"

    assert result["ready_to_execute"] is False

    assert (
        "field_area"
        in result["missing_context"]
    )

    assert (
        "state"
        in result["missing_context"]
    )

    assert (
        "district"
        in result["missing_context"]
    )


def test_complete_advisory_context_ready():

    result = plan_farmer_query(

        "Can I spray for banana Sigatoka today?",

        crop="Banana",

        pest="Sigatoka",

        field_area=0.5,

        area_unit="hectare",

        expected_harvest_days=30,

        growth_stage="vegetative",

        previous_application_count=0,

        state="Tamil Nadu",

        district="Coimbatore",
    )

    assert result["ready_to_execute"] is True

    assert result["missing_context"] == []
