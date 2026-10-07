"""The smoke-test script itself, run against the app in-process."""

import httpx
from fastapi.testclient import TestClient

from app.main import app
from scripts import smoke_test
from test_chat_orchestrator import RAIN_WEATHER, seeded  # noqa: F401


def _run(monkeypatch, message):
    smoke_test.results.clear()
    client = TestClient(app, base_url="http://testserver")
    session = smoke_test.check_chat(client, message)
    smoke_test.check_trace(client, session)
    smoke_test.check_whatsapp(client, None, None)
    smoke_test.check_health(client)
    return [(status, name) for status, name, _ in smoke_test.results]


def test_smoke_passes_on_recommend(monkeypatch):
    out = _run(monkeypatch, "rice blast 1 acre Erode, Tamil Nadu harvest in 40 days")
    assert not [item for item in out if item[0] == "FAIL"], out
    assert ("PASS", "chat: recommendation with dose") in out


def test_smoke_passes_on_delay_with_planned_dose(monkeypatch):
    monkeypatch.setattr("app.routers.advisory.get_location_weather", lambda **_: RAIN_WEATHER)
    out = _run(monkeypatch, "rice blast 1 acre Erode, Tamil Nadu harvest in 40 days")
    assert ("PASS", "chat: weather hold still shows planned dose") in out
    assert not [item for item in out if item[0] == "FAIL"], out
