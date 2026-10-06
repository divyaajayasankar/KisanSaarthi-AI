import sqlite3

from scripts.freeze_test_db import snapshot


def test_snapshot_keeps_reference_data_and_drops_personal_rows(tmp_path):
    live = tmp_path / "live.db"
    with sqlite3.connect(live) as conn:
        conn.execute("CREATE TABLE registry_entries (id INTEGER PRIMARY KEY, crop TEXT)")
        conn.execute("CREATE TABLE farmer_profiles (id INTEGER PRIMARY KEY, farmer_name TEXT)")
        conn.execute("CREATE TABLE conversation_sessions (id TEXT PRIMARY KEY, state_json TEXT)")
        conn.execute("INSERT INTO registry_entries (crop) VALUES ('Rice')")
        conn.execute("INSERT INTO farmer_profiles (farmer_name) VALUES ('Real Farmer')")
        conn.execute("INSERT INTO conversation_sessions VALUES ('s1', '{}')")

    target = tmp_path / "out" / "fixture.db"
    counts = snapshot(live, target)

    assert counts["registry_entries"] == 1
    assert counts["farmer_profiles"] == 0
    assert counts["conversation_sessions"] == 0

    # the live database is untouched
    with sqlite3.connect(live) as conn:
        assert conn.execute("SELECT COUNT(*) FROM farmer_profiles").fetchone()[0] == 1
