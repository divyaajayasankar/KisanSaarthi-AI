"""WhatsApp Cloud API adapter, exercised with simulated Meta payloads.

No live WhatsApp account is involved: the Graph API client is replaced by a
recorder, so these tests prove payload parsing, signature checking, session
continuity per phone number and the reply path, not delivery by Meta.
"""

import hashlib
import hmac
import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routers import whatsapp
from app.services.chat_orchestrator import ImageInput
from test_chat_orchestrator import RAIN_WEATHER, seeded  # noqa: F401  (autouse fixture)

client = TestClient(app)
SENDER = "919876543210"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"):
        monkeypatch.delenv(name, raising=False)


def payload(message):
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp", "messages": [message]}}]}]}


def text(body, sender=SENDER):
    return payload({"from": sender, "id": "wamid.1", "type": "text", "text": {"body": body}})


def post(body):
    return client.post("/api/whatsapp/webhook", json=body)


def test_verification_handshake(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "secret-token")
    ok = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "secret-token", "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"})
    assert bad.status_code == 403


def test_verification_refused_when_token_not_configured():
    response = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"})
    assert response.status_code == 403


def test_signature_required_when_secret_set(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    body = json.dumps(text("hello")).encode()
    assert client.post("/api/whatsapp/webhook", content=body).status_code == 403
    wrong = client.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64})
    assert wrong.status_code == 403
    good_sig = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    good = client.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": good_sig, "Content-Type": "application/json"})
    assert good.status_code == 200 and good.json()["messages"] == 1


def test_bad_json_is_rejected():
    assert client.post("/api/whatsapp/webhook", content=b"{not json").status_code == 400


def test_status_only_payload_is_acknowledged():
    body = {"entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "delivered"}]}}]}]}
    response = post(body)
    assert response.status_code == 200 and response.json()["messages"] == 0


def test_text_message_gets_a_reply_in_dry_run():
    result = post(text("My rice has blast")).json()
    assert result["dry_run"] is True
    item = result["results"][0]
    assert item["handled"] and item["sent"] is False and item["reason"] == "not_configured"
    assert "location" in item["reply"].lower() or "where" in item["reply"].lower()


def test_conversation_continues_per_phone_number_to_a_dose():
    for line in ("My rice has blast", "Coimbatore, Tamil Nadu", "2 acres", "30", "flowering"):
        post(text(line))
    final = post(text("no")).json()["results"][0]
    assert final["decision"] == "ANSWER"
    assert "Tricyclazole" in final["reply"] and "242.81" in final["reply"]


def test_two_numbers_do_not_share_a_session():
    post(text("My rice has blast", sender="911111111111"))
    post(text("Coimbatore, Tamil Nadu", sender="911111111111"))
    other = post(text("hello", sender="922222222222")).json()["results"][0]
    assert "Tricyclazole" not in other["reply"]


def test_delay_reply_over_whatsapp_includes_planned_dose(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    last = None
    for line in ("rice blast 2 acres Erode, Tamil Nadu harvest in 40 days vegetative", "no"):
        last = post(text(line, sender="933333333333")).json()["results"][0]
    assert "Do not spray now" in last["reply"]
    assert "Dose to use once conditions clear" in last["reply"] and "242.81" in last["reply"]


def test_shared_location_is_used_for_the_session():
    post(text("rice blast"))
    located = post(payload({"from": SENDER, "id": "w2", "type": "location",
                            "location": {"latitude": 11.0168, "longitude": 76.9558}})).json()["results"][0]
    assert located["handled"] is True and located["reply"]


def test_voice_note_gets_fixed_reply():
    item = post(payload({"from": SENDER, "id": "w3", "type": "audio", "audio": {"id": "m1"}})).json()["results"][0]
    assert "not supported" in item["reply"]


def test_unknown_type_gets_fixed_reply():
    item = post(payload({"from": SENDER, "id": "w4", "type": "sticker"})).json()["results"][0]
    assert "text, photos and shared locations" in item["reply"]


def test_photo_without_access_token_asks_to_resend():
    item = post(payload({"from": SENDER, "id": "w5", "type": "image", "image": {"id": "media-1"}})).json()["results"][0]
    assert "could not open the photo" in item["reply"]


def test_photo_with_caption_is_analysed(monkeypatch, tmp_path):
    from app.services import chat_orchestrator
    from app.services.vision_inference_service import VisionResult

    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        chat_orchestrator, "analyze_image",
        lambda crop, data: VisionResult(crop="rice", model_supported=True, prediction="blast",
                                        confidence=0.93, decision="ANSWER", reason="image_confidence_high"),
    )
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (30, 140, 40)).save(buffer, "JPEG")
    monkeypatch.setattr(whatsapp, "_download_photo", lambda media_id: ImageInput(buffer.getvalue(), "leaf.jpg", "image/jpeg"))
    item = post(payload({"from": SENDER, "id": "w6", "type": "image",
                         "image": {"id": "media-2", "caption": "rice leaves have spots"}})).json()["results"][0]
    assert "Photo result: Blast" in item["reply"]


class _Recorder:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        _Recorder.calls.append((url, headers, json))

        class _Ok:
            def raise_for_status(self):
                return None

        return _Ok()


def test_reply_is_sent_through_graph_api_when_configured(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "555")
    _Recorder.calls = []
    monkeypatch.setattr(whatsapp.httpx, "Client", _Recorder)
    response = post(text("My rice has blast")).json()
    assert "dry_run" not in response
    url, headers, body = _Recorder.calls[0]
    assert url.endswith("/555/messages")
    assert headers["Authorization"] == "Bearer token-123"
    assert body["to"] == SENDER and body["type"] == "text" and body["text"]["body"]


def test_reply_text_skips_info_messages_and_caps_length():
    turn = {"messages": [{"kind": "info", "text": "checking"}, {"kind": "advisory", "text": "x" * 5000}]}
    body = whatsapp.reply_text(turn)
    assert "checking" not in body and len(body) == whatsapp.MAX_BODY
