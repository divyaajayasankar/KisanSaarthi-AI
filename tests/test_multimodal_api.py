"""API-level tests for the chat page, status, vision analysis, voice and
protected translation. No network, no model downloads."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import speech_service, vision_inference_service
from app.services.language_service import protect, restore, translate_protected


client = TestClient(app)


def jpeg_bytes(size=(64, 48), color=(40, 160, 60)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


# ---------------------------------------------------------------- pages

def test_home_is_the_chat_page_with_all_controls():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for control in ("btnUpload", "btnCamera", "btnLocation", "btnSend", "lang", "text"):
        assert f'id="{control}"' in html
    assert "getUserMedia" in html
    assert "navigator.geolocation" in html
    assert "btnVoice" not in html  # microphone removed for now


def test_chat_page_never_uses_innerhtml():
    assert "innerHTML" not in client.get("/").text


def test_classic_route_exists_and_does_not_crash():
    assert client.get("/classic").status_code in (200, 404)


def test_status_reports_install_state():
    body = client.get("/api/status").json()
    for key in (
        "verified_registry_rows", "registry_crops", "real_field_eval_images",
        "vision_validated_crops", "speech_available", "llm_mode",
    ):
        assert key in body
    assert body["llm_mode"] in ("A", "B")


# ---------------------------------------------------------------- vision

def test_upload_endpoint_still_validates_only():
    response = client.post("/api/vision/upload", files={"image": ("leaf.jpg", jpeg_bytes(), "image/jpeg")})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Image accepted for visual analysis."
    assert "prediction" not in body


def test_analyze_unsupported_crop_abstains_without_a_diagnosis():
    response = client.post(
        "/api/vision/analyze",
        data={"crop": "tomato"},
        files={"image": ("leaf.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_supported"] is False
    assert body["prediction"] is None
    assert body["confidence"] is None
    assert body["decision"] == "ABSTAIN"
    assert "not currently validated" in body["message"]


def test_analyze_rejects_invalid_image():
    response = client.post(
        "/api/vision/analyze",
        data={"crop": "rice"},
        files={"image": ("x.jpg", b"not an image", "image/jpeg")},
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "probabilities, expected_label, expected",
    [
        ([0.93, 0.05, 0.02], "early_blight", "ANSWER"),
        ([0.70, 0.20, 0.10], "early_blight", "ASK_FOLLOW_UP"),
        ([0.30, 0.28, 0.42], "healthy", "ABSTAIN"),
    ],
)
def test_analyze_confidence_gates_with_a_validated_model(monkeypatch, probabilities, expected_label, expected):
    entry = {
        "validated": True,
        "labels": ["early_blight", "late_blight", "healthy"],
        "architecture": "mobilenet_v3_small",
        "path": "x",
    }
    monkeypatch.setattr(vision_inference_service, "registry_entry", lambda crop: entry)
    monkeypatch.setattr(vision_inference_service, "get_predictor", lambda crop: (lambda image: probabilities))

    response = client.post(
        "/api/vision/analyze",
        data={"crop": "tomato"},
        files={"image": ("leaf.jpg", jpeg_bytes(), "image/jpeg")},
    )
    body = response.json()
    assert body["model_supported"] is True
    assert body["prediction"] == expected_label
    assert body["confidence"] == pytest.approx(max(probabilities))
    assert body["decision"] == expected


def test_models_endpoint_lists_only_validated_crops():
    body = client.get("/api/vision/models").json()
    assert body["validated_crops"] == sorted(body["validated_crops"])


# ---------------------------------------------------------------- voice

class _Segment:
    def __init__(self, text):
        self.text = text


class _Info:
    language = "ta"
    language_probability = 0.97
    duration = 3.2


class _FakeModel:
    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        return [_Segment("என் மிளகாய் இலைகள் சுருண்டு வருகின்றன")], _Info()


def test_transcribe_returns_text_for_confirmation_and_sends_nothing(monkeypatch):
    monkeypatch.setattr(speech_service, "get_model", lambda: _FakeModel())
    response = client.post("/api/speech/transcribe", files={"audio": ("v.webm", b"\x1aE\xdf\xa3fake", "audio/webm")})
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "ta"
    assert body["requires_confirmation"] is True
    assert "மிளகாய்" in body["text"]


def test_transcribe_uses_language_hint(monkeypatch):
    model = _FakeModel()
    monkeypatch.setattr(speech_service, "get_model", lambda: model)
    client.post(
        "/api/speech/transcribe",
        data={"language": "hi"},
        files={"audio": ("v.webm", b"fake", "audio/webm")},
    )
    assert model.kwargs["language"] == "hi"
    assert model.kwargs["task"] == "transcribe"


def test_transcribe_rejects_empty_oversized_and_wrong_type(monkeypatch):
    monkeypatch.setattr(speech_service, "get_model", lambda: _FakeModel())
    assert client.post("/api/speech/transcribe", files={"audio": ("v.webm", b"", "audio/webm")}).status_code == 400
    assert client.post("/api/speech/transcribe", files={"audio": ("v.txt", b"hello", "text/plain")}).status_code == 400

    monkeypatch.setattr(speech_service.settings, "max_audio_mb", 0)
    assert client.post("/api/speech/transcribe", files={"audio": ("v.webm", b"abc", "audio/webm")}).status_code == 400


def test_transcribe_reports_unavailable_model_as_503(monkeypatch):
    def broken():
        raise speech_service.SpeechUnavailableError("model could not be loaded")

    monkeypatch.setattr(speech_service, "get_model", broken)
    response = client.post("/api/speech/transcribe", files={"audio": ("v.webm", b"fake", "audio/webm")})
    assert response.status_code == 503
    assert "could not be loaded" in response.json()["detail"]


# ---------------------------------------------------------------- protected translation

SAMPLE = "Apply Tricyclazole 242.81 g per 2 acre. PHI is 14 days. Next spray after 2026-10-20."


def test_protect_masks_dose_unit_date_and_ingredient_and_restores_exactly():
    masked, mapping = protect(SAMPLE, ["Tricyclazole"])
    for value in ("Tricyclazole", "242.81 g", "14 days", "2026-10-20"):
        assert value not in masked
        assert value in mapping.values()
    assert restore(masked, mapping) == SAMPLE


def test_translation_that_drops_a_marker_is_rejected():
    def lossy(masked, language):
        return masked.replace("⟦1⟧", "")

    text, translated = translate_protected(SAMPLE, "ta", lossy, ["Tricyclazole"])
    assert translated is False and text == SAMPLE


def test_translation_that_keeps_markers_succeeds_and_values_stay_exact():
    def upper(masked, language):
        return "[ta] " + masked

    text, translated = translate_protected(SAMPLE, "ta", upper, ["Tricyclazole"])
    assert translated is True
    assert "Tricyclazole" in text and "242.81 g" in text and "14 days" in text and "2026-10-20" in text


def test_no_translator_returns_original():
    assert translate_protected(SAMPLE, "hi", None) == (SAMPLE, False)
