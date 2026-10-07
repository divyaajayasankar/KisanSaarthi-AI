"""Trace persistence, saved profile and the guarantee that storage never breaks a reply."""

from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app
from app.services import trace_service

from test_chat_orchestrator import converse, seeded  # noqa: F401  (autouse fixture: seeded registry, mocked weather)

client = TestClient(app)


def _chat_to_answer():
    return converse([
        "rice blast 2 acres Coimbatore, Tamil Nadu harvest in 60 days",
        "vegetative",
        "no",
    ])


def test_each_turn_is_traced_with_decision_and_rules():
    reply = _chat_to_answer()
    sid = reply["session_id"]
    body = client.get(f"/api/chat/trace/{sid}").json()
    assert len(body["turns"]) >= 3
    last = body["turns"][-1]
    assert last["decision"] == reply["decision"]
    assert last["user_text"] == "no"
    assert isinstance(last["trace_json"], list) and last["trace_json"]
    assert last["engine_status"] in (reply["advisory"] or {}).get("status", last["engine_status"])
    assert isinstance(last["fired_rules"], list)
    assert last["latency_ms"] is not None and last["latency_ms"] >= 0


def test_saved_profile_matches_the_conversation():
    reply = _chat_to_answer()
    profile = client.get(f"/api/chat/profile/{reply['session_id']}").json()
    assert profile["crop"].lower() == "rice"
    assert profile["land_area"] == 2
    assert profile["land_unit"] == "acre"
    assert profile["growth_stage"] == "vegetative"
    assert profile["state"] == "Tamil Nadu"
    assert profile["last_decision"] == reply["decision"]


def test_unknown_session_has_no_profile():
    assert client.get("/api/chat/profile/does-not-exist").status_code == 404


def test_storage_failure_never_changes_the_reply(monkeypatch):
    baseline = _chat_to_answer()

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(trace_service, "ensure_tables", boom)
    after = _chat_to_answer()
    assert after["decision"] == baseline["decision"]
    assert [m["text"] for m in after["messages"]][-3:] == [m["text"] for m in baseline["messages"]][-3:]


def test_packaged_database_snapshot_empties_trace_and_profile_tables(tmp_path):
    import sqlite3
    from contextlib import closing

    from scripts.freeze_test_db import PERSONAL_TABLES, snapshot

    assert "advisory_traces" in PERSONAL_TABLES and "field_profiles" in PERSONAL_TABLES
    source = tmp_path / "live.db"
    with closing(sqlite3.connect(source)) as conn:
        conn.execute("CREATE TABLE advisory_traces (id INTEGER, user_text TEXT)")
        conn.execute("CREATE TABLE field_profiles (session_id TEXT, crop TEXT)")
        conn.execute("CREATE TABLE registry_entries (id INTEGER)")
        conn.execute("INSERT INTO advisory_traces VALUES (1, 'my rice has blast')")
        conn.execute("INSERT INTO field_profiles VALUES ('s', 'Rice')")
        conn.execute("INSERT INTO registry_entries VALUES (1)")
        conn.commit()
    counts = snapshot(source, tmp_path / "clean.db")
    assert counts["advisory_traces"] == 0 and counts["field_profiles"] == 0 and counts["registry_entries"] == 1
