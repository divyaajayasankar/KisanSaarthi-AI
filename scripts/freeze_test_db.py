"""Snapshot the live kisansaarthi.db into tests/fixtures/ for test isolation.

    python -m scripts.freeze_test_db

Run after any ingest/migration script changes the live database.

The snapshot keeps reference data only (registry, rules, provenance).
Rows that can hold personal data (farmer profiles, advisory runs, chat
sessions) are emptied in the COPY; the live database is never changed.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = PROJECT_ROOT / "kisansaarthi.db"
FIXTURE_DB = PROJECT_ROOT / "tests" / "fixtures" / "kisansaarthi_test.db"

PERSONAL_TABLES = ("farmer_profiles", "advisory_runs", "conversation_sessions")


def snapshot(source: Path, target: Path) -> dict[str, int]:
    """Consistent copy of `source` at `target` with personal tables emptied.
    Returns row counts per table."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    # closing() releases the file handle; "with sqlite3.connect()" only commits.
    # An open handle makes temp-directory cleanup fail on Windows.
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)

    counts: dict[str, int] = {}
    with closing(sqlite3.connect(target)) as conn:
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ]
        for table in PERSONAL_TABLES:
            if table in tables:
                conn.execute(f'DELETE FROM "{table}"')
        conn.commit()
        for table in tables:
            counts[table] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        conn.execute("VACUUM")
    return counts


def main() -> None:
    if not LIVE_DB.exists():
        raise SystemExit(f"Live database not found: {LIVE_DB}")

    counts = snapshot(LIVE_DB, FIXTURE_DB)
    print(f"Frozen {LIVE_DB.name} -> {FIXTURE_DB.relative_to(PROJECT_ROOT)} (personal tables emptied)")
    for table, count in counts.items():
        print(f"  {table:<28} {count}")


if __name__ == "__main__":
    main()
