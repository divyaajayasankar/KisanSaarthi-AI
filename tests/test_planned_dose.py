"""Dose shown when the weather says wait, and photo affected-region output.

A weather delay or an unverified forecast must still tell the farmer which
product and how much to use once conditions clear, marked "do not apply now".
Any other blocker (PHI, growth stage, interval, application cap) must still
show no dose at all.
"""

import pytest

from app.services import weather_service
from test_chat_orchestrator import (  # noqa: F401  (fixtures and helpers)
    RAIN_WEATHER,
    all_text,
    converse,
    say,
    seeded,
)

RICE = "rice blast 1 acre Erode, Tamil Nadu harvest in 40 days vegetative"


def test_rain_delay_still_shows_planned_dose(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    reply = converse(["rice blast 2 acres Erode, Tamil Nadu harvest in 40 days vegetative", "no"])
    assert reply["decision"] == "ANSWER"
    assert reply["advisory"]["status"] == "delay"
    assert reply["advisory"]["active_ingredient"] is None  # engine result unchanged
    planned = reply["advisory"]["planned_dose"]
    assert planned["active_ingredient"] == "Tricyclazole"
    assert planned["dose_min"] == pytest.approx(242.81, abs=0.01)
    assert planned["apply_now"] is False
    text = all_text(reply)
    assert "Do not spray now" in text
    assert "Dose to use once conditions clear" in text and "242.81" in text and "Tricyclazole" in text
    assert "Do not apply it now" in text


def test_wind_delay_also_shows_planned_dose(monkeypatch):
    windy = {"weather": {**RAIN_WEATHER["weather"], "rain_total_mm": 0.0, "max_rain_probability": 0.1,
                         "max_wind_speed_m_s": 5.0}, "source": "test"}
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: windy)
    reply = converse([RICE, "no"])
    assert reply["advisory"]["status"] == "delay"
    assert reply["advisory"]["planned_dose"]["dose_min"] == pytest.approx(121.41, abs=0.01)


def test_weather_unavailable_abstains_but_shows_planned_dose(monkeypatch):
    def fail(**_):
        raise weather_service.WeatherServiceError("no forecast")

    monkeypatch.setattr("app.routers.advisory.get_location_weather", fail)
    reply = converse([RICE, "no"])
    assert reply["decision"] == "ABSTAIN"
    assert "weather_unavailable" in reply["advisory"]["fired_rules"]
    text = all_text(reply)
    assert "could not be verified" in text
    assert "Dose to use once conditions clear" in text and "121.41" in text


def test_phi_failure_shows_no_dose():
    reply = converse(["rice blast 1 acre Erode, Tamil Nadu harvest in 5 days vegetative", "no"])
    assert reply["decision"] == "ABSTAIN"
    assert "planned_dose" not in reply["advisory"]
    assert "Dose to use once conditions clear" not in all_text(reply)


def test_phi_failure_under_rain_shows_no_dose(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    reply = converse(["rice blast 1 acre Erode, Tamil Nadu harvest in 5 days vegetative", "no"])
    assert "planned_dose" not in reply["advisory"]
    assert "Dose to use once conditions clear" not in all_text(reply)


def test_normal_recommendation_has_no_planned_dose():
    reply = converse([RICE, "no"])
    assert reply["advisory"]["status"] == "recommend"
    assert "planned_dose" not in reply["advisory"]


def test_hindi_delay_includes_planned_dose(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    reply = converse(["चावल में ब्लास्ट है", "Erode, Tamil Nadu", "1 acre", "40", "vegetative", "no"], language="hi")
    assert reply["advisory"]["status"] == "delay"
    text = all_text(reply)
    assert "Tricyclazole" in text and "121.41" in text


def test_planned_dose_is_recorded_in_trace(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    reply = converse([RICE, "no"])
    agents = [step["agent"] for step in reply["agent_trace"]]
    assert "Planned Dose" in agents


# ------------------------------------------------------------------
# Affected region (Grad-CAM)
# ------------------------------------------------------------------

from app.services import vision_region_service as region  # noqa: E402


def test_describe_position_nine_cells():
    assert region.describe_position(0.1, 0.1) == "upper_left"
    assert region.describe_position(0.5, 0.5) == "center"
    assert region.describe_position(0.9, 0.9) == "lower_right"
    assert region.describe_position(1.0, 0.0) == "upper_right"
    assert region.describe_position(0.5, 0.95) == "lower_center"


def test_region_from_cam_finds_hot_corner():
    cam = [[0.0] * 7 for _ in range(7)]
    cam[0][0] = cam[0][1] = cam[1][0] = cam[1][1] = 1.0
    found = region.region_from_cam(cam, (0.0, 0.0, 1.0, 1.0))
    assert found["position"] == "upper_left"
    assert found["share_of_view_percent"] == round(100 * 4 / 49)
    assert found["box"] == [0.0, 0.0, pytest.approx(2 / 7, abs=0.001), pytest.approx(2 / 7, abs=0.001)]
    assert "not a measured lesion" in found["method"]


def test_region_from_cam_maps_through_crop_box():
    cam = [[0.0] * 4 for _ in range(4)]
    cam[3][3] = 1.0
    found = region.region_from_cam(cam, (0.25, 0.0, 0.75, 1.0))
    assert found["position"] == "lower_right" or found["position"] == "lower_center"
    assert 0.25 <= found["center"][0] <= 0.75


def test_region_from_cam_rejects_empty_and_flat():
    assert region.region_from_cam([], (0, 0, 1, 1)) is None
    assert region.region_from_cam([[0.0, 0.0], [0.0, 0.0]], (0, 0, 1, 1)) is None


def test_view_box_for_wide_photo():
    left, top, right, bottom = region._view_box(400, 200, 224)
    assert top == pytest.approx(0.5 * (1 - 224 / int(224 * 1.14)), abs=1e-6)
    assert left > top  # a wide photo loses more width than height
    assert right == pytest.approx(1 - left) and bottom == pytest.approx(1 - top)


def test_compute_cam_and_locate_with_random_weights(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from io import BytesIO

    from PIL import Image

    from app.services import vision_inference_service as vis

    labels = ["healthy", "sigatoka"]
    model = vis.build_model("mobilenet_v3_small", len(labels)).eval()
    tensor = torch.randn(1, 3, 224, 224)
    grid = region.compute_cam(model, tensor, 1)
    assert grid and all(0.0 <= v <= 1.0 for row in grid for v in row)

    entry = {"architecture": "mobilenet_v3_small", "labels": labels, "input_size": 224, "path": "app/main.py"}
    monkeypatch.setattr(vis, "registry_entry", lambda crop: entry if crop == "banana" else None)
    monkeypatch.setattr(vis, "torch_available", lambda: True)
    monkeypatch.setattr(region, "_load", lambda crop, path, mtime: (model, vis.eval_transform(224), entry))

    buffer = BytesIO()
    Image.new("RGB", (300, 200), (40, 150, 60)).save(buffer, "JPEG")
    found = region.locate_affected_region("banana", buffer.getvalue(), "sigatoka", overlay_dir=tmp_path)
    assert found is None or found["position"] in {name for row in region.GRID_NAMES for name in row}
    if found:
        assert (tmp_path / "affected_region.png").exists()
    assert region.locate_affected_region("banana", b"not an image", "sigatoka") is None
    assert region.locate_affected_region("rice", buffer.getvalue(), "blast") is None
    assert region.locate_affected_region("banana", buffer.getvalue(), "unknown_label") is None


def test_photo_reply_names_disease_and_region(tmp_path, monkeypatch):
    from io import BytesIO

    from PIL import Image

    from app.services import chat_orchestrator
    from app.services.vision_inference_service import VisionResult

    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        chat_orchestrator, "analyze_image",
        lambda crop, data: VisionResult(crop="rice", model_supported=True, prediction="blast",
                                        confidence=0.93, decision="ANSWER", reason="image_confidence_high"),
    )
    monkeypatch.setattr(
        "app.services.vision_region_service.locate_affected_region",
        lambda crop, data, label, overlay_dir=None: {
            "position": "upper_left", "center": [0.2, 0.2], "box": [0, 0, 0.4, 0.4],
            "share_of_view_percent": 18, "method": "grad-cam (model attention, not a measured lesion area)"},
    )
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (30, 140, 40)).save(buffer, "JPEG")
    from fastapi.testclient import TestClient
    from app.main import app

    reply = TestClient(app).post(
        "/api/chat/turn",
        data={"text": "rice, 1 acre, Erode, Tamil Nadu, harvest in 40 days, vegetative, no spray"},
        files={"image": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    ).json()
    text = all_text(reply)
    assert "Photo result: Blast" in text
    assert "Most affected area: upper left, about 18%" in text
    assert reply["vision"]["region"]["position"] == "upper_left"


def test_healthy_leaf_reports_no_region(tmp_path, monkeypatch):
    from io import BytesIO

    from PIL import Image

    from app.services import chat_orchestrator
    from app.services.vision_inference_service import VisionResult

    monkeypatch.setattr(chat_orchestrator, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        chat_orchestrator, "analyze_image",
        lambda crop, data: VisionResult(crop="banana", model_supported=True, prediction="healthy",
                                        confidence=0.97, decision="ANSWER", reason="image_confidence_high"),
    )
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (30, 140, 40)).save(buffer, "JPEG")
    from fastapi.testclient import TestClient
    from app.main import app

    reply = TestClient(app).post(
        "/api/chat/turn", data={"text": "banana leaf check"},
        files={"image": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
    ).json()
    assert "looks healthy" in all_text(reply)
