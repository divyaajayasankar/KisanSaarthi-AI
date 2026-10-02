# C:\farmer\tests\test_agent_specialist_execution.py

from types import SimpleNamespace

from app.services import agent_executor


# ============================================================
# 1. WEATHER SPECIALIST
# ============================================================

def test_weather_specialist(monkeypatch):

    def fake_weather(
        *,
        district,
        state,
    ):
        return {
            "weather": {
                "temperature_c": 28.0,
                "wind_speed_m_s": 2.0,
                "rain_mm": 0.0,
            },
            "source": "test_weather",
        }

    fake_rule_result = SimpleNamespace(
        status="recommend",
        explanation="Weather conditions are suitable.",
        fired_rules=[
            "weather_passed"
        ],
    )

    monkeypatch.setattr(
        agent_executor,
        "get_location_weather",
        fake_weather,
    )

    monkeypatch.setattr(
        agent_executor,
        "evaluate_weather_safety",
        lambda weather: fake_rule_result,
    )

    result = (
        agent_executor
        .execute_weather_specialist(
            state="Tamil Nadu",
            district="Coimbatore",
        )
    )

    assert result["status"] == "completed"

    assert result["tool"] == "weather"

    assert (
        result["spray_safety"]["status"]
        == "recommend"
    )


# ============================================================
# 2. SOIL SPECIALIST
# ============================================================

def test_soil_specialist(monkeypatch):

    def fake_soil(
        *,
        latitude,
        longitude,
    ):
        return {
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "root_zone_depth": "0-30 cm",
            "root_zone": {
                "ph": 6.5,
            },
            "aggregation": "weighted_mean",
            "source": "test_soil",
        }

    monkeypatch.setattr(
        agent_executor,
        "get_root_zone_soil_context",
        fake_soil,
    )

    result = (
        agent_executor
        .execute_soil_specialist(
            latitude=11.0168,
            longitude=76.9558,
        )
    )

    assert result["status"] == "completed"

    assert result["tool"] == "soil"

    assert (
        result["soil"]["root_zone"]["ph"]
        == 6.5
    )


# ============================================================
# 3. VERIFIED RAG SPECIALIST
# ============================================================

def test_knowledge_specialist(monkeypatch):

    def fake_rag(
        *,
        query,
        crop,
        top_k,
    ):
        return {
            "status": "retrieved",
            "results": [
                {
                    "crop": crop,
                    "topic": "Blast",
                    "verified": True,
                    "text":
                        "Verified rice blast evidence.",
                }
            ],
        }

    monkeypatch.setattr(
        agent_executor,
        "retrieve_verified_evidence",
        fake_rag,
    )

    result = (
        agent_executor
        .execute_knowledge_specialist(
            question=(
                "How can I manage rice blast?"
            ),
            crop="Rice",
        )
    )

    assert result["status"] == "completed"

    assert result["tool"] == "verified_rag"

    assert (
        result["result"]["status"]
        == "retrieved"
    )


# ============================================================
# 4. WEATHER MISSING CONTEXT
# ============================================================

def test_weather_missing_context():

    result = (
        agent_executor
        .execute_weather_specialist(
            state=None,
            district=None,
        )
    )

    assert (
        result["status"]
        == "needs_context"
    )

    assert (
        "state"
        in result["missing_context"]
    )

    assert (
        "district"
        in result["missing_context"]
    )


# ============================================================
# 5. SOIL MISSING COORDINATES
# ============================================================

def test_soil_missing_coordinates():

    result = (
        agent_executor
        .execute_soil_specialist(
            latitude=None,
            longitude=None,
        )
    )

    assert (
        result["status"]
        == "needs_context"
    )

    assert (
        "latitude_longitude"
        in result["missing_context"]
    )