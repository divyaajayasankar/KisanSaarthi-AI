"""End-to-end conversation tests through /api/chat with a seeded in-memory
registry. Weather is mocked; everything else (alias layer, extraction,
engine, PHI, dose scaling, decision controller) runs for real."""

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models_conversation  # noqa: F401
from app.db import Base, get_db
from app.main import app
from app.models import RegistryEntry
from app.models_resistance import ResistanceRule
from app.services import chat_orchestrator, location_service, weather_service
from app.services.vision_inference_service import VisionResult


ENGINE = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


def _registry(crop, pest, ai, dmin, dmax, unit, phi, phi_na=False):
    return RegistryEntry(
        crop=crop, pest=pest, active_ingredient=ai, formulation="TEST",
        dose_min_per_hectare=dmin, dose_max_per_hectare=dmax, dose_unit=unit,
        phi_days=phi, phi_not_applicable=phi_na, source_document="TEST FIXTURE",
        source_page=1, source_url="https://example.org/fixture", verified=True, is_test_data=False,
    )


@pytest.fixture(autouse=True)
def seeded(monkeypatch):
    Base.metadata.drop_all(bind=ENGINE)
    Base.metadata.create_all(bind=ENGINE)
    with TestingSession() as db:
        db.add_all(
            [
                _registry("Rice", "Blast; Sheath blight", "Tricyclazole", 300, 300, "g", 14),
                _registry("Chilli", "Thrips; Mites", "Fipronil", 800, 1000, "ml", 7),
                _registry("Banana", "Sigatoka", "Propiconazole", 500, 500, "ml", 0, phi_na=True),
                ResistanceRule(
                    crop="Chilli", pest="Thrips; Mites", active_ingredient="Fipronil", framework="IRAC",
                    moa_group="2B", moa_name="Phenylpyrazoles", resistance_risk="high", rotation_recommended=True,
                    verified=True, source_name="IRAC", source_url="https://irac-online.org/", notes="fixture",
                ),
                ResistanceRule(
                    crop="Chilli", pest="Thrips; Mites", active_ingredient="Ethiprole", framework="IRAC",
                    moa_group="2B", moa_name="Phenylpyrazoles", resistance_risk="high", rotation_recommended=True,
                    verified=True, source_name="IRAC", source_url="https://irac-online.org/", notes="fixture",
                ),
            ]
        )
        db.commit()

    def override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(weather_service, "OPENWEATHER_API_KEY", None)
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: SAFE_WEATHER)
    yield
    app.dependency_overrides.clear()


SAFE_WEATHER = {
    "weather": {
        "rain_total_mm": 0.0, "max_rain_probability": 0.1, "max_wind_speed_m_s": 1.5,
        "min_temperature_c": 22, "max_temperature_c": 31, "city": "Coimbatore",
    },
    "source": "test",
}
RAIN_WEATHER = {
    "weather": {
        "rain_total_mm": 12.0, "max_rain_probability": 0.9, "max_wind_speed_m_s": 1.0,
        "min_temperature_c": 22, "max_temperature_c": 28, "city": "Coimbatore",
    },
    "source": "test",
}

client = TestClient(app)


def say(text, session=None, language="auto"):
    response = client.post("/api/chat/message", json={"session_id": session, "text": text, "language": language})
    assert response.status_code == 200, response.text
    return response.json()


def converse(lines, language="auto"):
    session, reply = None, None
    for line in lines:
        reply = say(line, session, language)
        session = reply["session_id"]
    return reply


def all_text(reply):
    return "\n".join(message["text"] for message in reply["messages"])


# ------------------------------------------------------------------
# Multi-turn memory and ordered follow-ups
# ------------------------------------------------------------------

def test_multi_turn_english_reaches_answer_with_scaled_dose():
    first = say("My rice has blast")
    assert first["decision"] == "ASK_FOLLOW_UP" and first["follow_up_field"] == "location"
    sid = first["session_id"]
    assert say("Coimbatore, Tamil Nadu", sid)["follow_up_field"] == "land_area"
    assert say("2 acres", sid)["follow_up_field"] == "harvest_days"
    assert say("30", sid)["follow_up_field"] == "growth_stage"
    assert say("flowering", sid)["follow_up_field"] == "previous_treatment"
    final = say("no", sid)

    assert final["decision"] == "ANSWER"
    assert final["advisory"]["status"] == "recommend"
    assert final["advisory"]["active_ingredient"] == "Tricyclazole"
    # 300 g/ha x 2 acre (0.809 ha) = 242.81 g, computed by the engine
    assert final["advisory"]["scaled_dose_min"] == pytest.approx(242.81, abs=0.01)
    text = all_text(final)
    assert "242.81" in text and "Tricyclazole" in text
    assert "bees" in text  # flowering -> pollinator note
    context = final["context"]
    assert context["crop"] == "Rice" and context["pest"] == "Blast" and context["location"] == "Coimbatore, Tamil Nadu"


def test_never_asks_twice_for_supplied_values():
    reply = say("Rice blast, 1 hectare in Madurai, Tamil Nadu, harvest in 40 days, vegetative stage, no previous spray")
    assert reply["decision"] == "ASK_FOLLOW_UP"
    assert reply["follow_up_field"] == "previous_treatment"
    final = say("no", reply["session_id"])
    assert final["decision"] == "ANSWER"
    asked = [step.get("follow_up_field") for step in final["agent_trace"] if step["agent"] == "Decision Controller"]
    assert "location" not in asked and "land_area" not in asked


def test_land_area_without_unit_asks_for_unit():
    reply = converse(["rice blast", "Salem, Tamil Nadu", "3"])
    assert reply["follow_up_field"] == "land_unit"
    assert say("hectare", reply["session_id"])["follow_up_field"] == "harvest_days"


def test_location_without_state_asks_for_state():
    reply = converse(["rice blast", "Coimbatore"])
    assert reply["follow_up_field"] == "location"
    assert "Tamil Nadu" in all_text(reply)
    assert say("Tamil Nadu", reply["session_id"])["follow_up_field"] == "land_area"


# ------------------------------------------------------------------
# Safety outcomes
# ------------------------------------------------------------------

def test_phi_violation_abstains():
    reply = converse(["rice blast 1 acre Erode, Tamil Nadu harvest in 5 days vegetative", "no"])
    assert reply["decision"] == "ABSTAIN"
    assert "phi_rejected" in reply["advisory"]["fired_rules"]
    assert "14" in all_text(reply) and "5" in all_text(reply)


def test_rain_gives_delay_answer(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    reply = converse(["rice blast 1 acre Erode, Tamil Nadu harvest in 40 days vegetative", "no"])
    assert reply["decision"] == "ANSWER"
    assert reply["advisory"]["status"] == "delay"
    assert reply["advisory"]["active_ingredient"] is None
    assert "Do not spray now" in all_text(reply)


def test_unregistered_pest_abstains_without_asking_more():
    reply = say("rice brown spot problem")
    assert reply["decision"] == "ABSTAIN"
    assert reply["reason"] == "engine_abstain:registration_missing"


def test_phi_not_applicable_crop_answers():
    reply = converse(["banana sigatoka 1 acre Theni, Tamil Nadu harvest in 3 days vegetative", "no"])
    assert reply["decision"] == "ANSWER"
    assert "not applicable" in all_text(reply)
    assert reply["advisory"]["fired_rules"].count("phi_passed") == 0


def test_same_active_ingredient_needs_interval():
    reply = converse(["chilli thrips 1 acre Guntur, Andhra Pradesh harvest in 30 days fruiting, sprayed fipronil"])
    assert reply["decision"] == "ASK_FOLLOW_UP"
    assert reply["follow_up_field"] == "days_since_last_application"
    final = say("10", reply["session_id"])
    history = [step for step in final["agent_trace"] if step["agent"] == "Treatment History Agent"][0]
    assert history["same_active_ingredient"] is True
    assert history["previous_application_count"] == 1
    assert history["days_since_last_application"] == 10


def test_same_moa_group_warning():
    reply = converse(["chilli thrips 1 acre Guntur, Andhra Pradesh harvest in 30 days fruiting, sprayed ethiprole last week"])
    assert reply["decision"] == "ANSWER"
    assert "2B" in all_text(reply) and "ethiprole" in all_text(reply).lower()


# ------------------------------------------------------------------
# Multilingual
# ------------------------------------------------------------------

def test_tamil_conversation_replies_in_tamil():
    reply = converse(["நெல்லில் குலை நோய், 2 ஏக்கர், அறுவடைக்கு 30 நாட்கள்", "Coimbatore, Tamil Nadu", "வளர்ச்சி பருவம்", "இல்லை"])
    assert reply["language"] == "ta"
    assert reply["decision"] == "ANSWER"
    text = all_text(reply)
    assert "செயல் மூலப்பொருள்" in text
    assert "Tricyclazole" in text and "242.81" in text  # protected values unchanged


def test_hindi_and_telugu_detection():
    assert say("मेरी मिर्च की पत्तियाँ मुड़ रही हैं।")["language"] == "hi"
    assert say("నా మిరప ఆకులు ముడుచుకుంటున్నాయి.")["language"] == "te"


def test_explicit_language_overrides_detection():
    reply = say("my rice has blast", language="hi")
    assert reply["language"] == "hi"
    assert "खेत" in all_text(reply)


# ------------------------------------------------------------------
# Image path
# ------------------------------------------------------------------

def _jpeg():
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (30, 140, 40)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_symptom_only_then_unsupported_image_then_abstain(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    first = say("my okra leaves are curling")
    assert first["follow_up_field"] == "photo"
    sid = first["session_id"]
    upload = client.post(
        "/api/chat/turn",
        data={"session_id": sid},
        files={"image": ("leaf.jpg", _jpeg(), "image/jpeg")},
    ).json()
    assert upload["vision"]["model_supported"] is False
    assert upload["follow_up_field"] == "pest_name"
    assert "not yet validated" in all_text(upload)
    final = say("I don't know", sid)
    assert final["decision"] == "ABSTAIN" and final["reason"] == "pest_unknown"


def test_medium_confidence_vision_asks_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        chat_orchestrator,
        "analyze_image",
        lambda crop, data: VisionResult(crop="rice", model_supported=True, prediction="blast",
                                        confidence=0.66, decision="ASK_FOLLOW_UP", reason="image_confidence_medium"),
    )
    reply = client.post(
        "/api/chat/turn",
        data={"text": "rice leaves have spots"},
        files={"image": ("leaf.jpg", _jpeg(), "image/jpeg")},
    ).json()
    assert reply["follow_up_field"] == "confirm_pest"
    assert "66%" in all_text(reply)
    after = say("yes", reply["session_id"])
    assert after["context"]["pest"] == "Blast" and after["context"]["pest_source"] == "vision_confirmed"
    assert after["follow_up_field"] == "location"


def test_high_confidence_vision_sets_pest(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        chat_orchestrator,
        "analyze_image",
        lambda crop, data: VisionResult(crop="rice", model_supported=True, prediction="blast",
                                        confidence=0.93, decision="ANSWER", reason="image_confidence_high"),
    )
    reply = client.post(
        "/api/chat/turn",
        data={"text": "rice, 1 acre, Erode, Tamil Nadu, harvest in 40 days, vegetative, no spray"},
        files={"image": ("leaf.jpg", _jpeg(), "image/jpeg")},
    ).json()
    if reply["decision"] == "ASK_FOLLOW_UP":
        reply = say("no", reply["session_id"])
    assert reply["decision"] == "ANSWER"
    assert "93%" in all_text(reply)


def test_invalid_image_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    reply = client.post(
        "/api/chat/turn", data={"text": "rice"}, files={"image": ("x.jpg", b"not an image", "image/jpeg")}
    ).json()
    assert any("could not be used" in message["text"] for message in reply["messages"])


# ------------------------------------------------------------------
# Location by GPS, reset, greeting
# ------------------------------------------------------------------

def test_gps_without_key_keeps_coordinates_and_asks_place(monkeypatch):
    first = say("rice blast")
    reply = client.post(
        "/api/chat/message", json={"session_id": first["session_id"], "latitude": 11.0168, "longitude": 76.9558}
    ).json()
    assert reply["follow_up_field"] == "location"
    assert reply["context"]["latitude"] == pytest.approx(11.0168)


def test_gps_with_reverse_geocoding(monkeypatch):
    monkeypatch.setattr(
        location_service, "resolve_coordinates",
        lambda lat, lon: location_service.ResolvedLocation("resolved", "Coimbatore", "Coimbatore", "Tamil Nadu", lat, lon, "test"),
    )
    monkeypatch.setattr(chat_orchestrator, "resolve_coordinates", location_service.resolve_coordinates)
    first = say("rice blast")
    reply = client.post(
        "/api/chat/message", json={"session_id": first["session_id"], "latitude": 11.0, "longitude": 76.9}
    ).json()
    assert reply["follow_up_field"] == "land_area"
    assert reply["context"]["location"] == "Coimbatore, Tamil Nadu"


def test_reset_clears_context():
    first = say("rice blast")
    reply = say("start over", first["session_id"])
    assert reply["context"]["crop"] is None


def test_greeting():
    reply = say("hello")
    assert reply["follow_up_field"] == "crop"
    assert "KisanSaarthi" in all_text(reply)


def test_session_endpoint_returns_history():
    first = say("rice blast")
    data = client.get(f"/api/chat/session/{first['session_id']}").json()
    assert data["context"]["crop"] == "Rice"
    assert data["history"][0]["role"] == "user"


def test_harvest_days_age_between_turns():
    from app.services import conversation_service as conv

    assert conv.aged_days(30, "2026-10-01", date(2026, 10, 5), -1) == 26
    assert conv.aged_days(7, "2026-10-01", date(2026, 10, 5), +1) == 11
