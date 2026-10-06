"""Test database isolation.

This module is imported by pytest before any test module, so it runs
before app.config / app.db create the engine. It points DATABASE_URL
at a throwaway copy of the database, so tests can never read a
half-edited live DB or write into it.

Source of the copy, in order:
  1. tests/fixtures/kisansaarthi_test.db  (frozen, versioned snapshot)
  2. ./kisansaarthi.db                     (live DB, fallback only)
  3. nothing -> empty DB; data-dependent tests will fail loudly

Refresh the frozen snapshot after re-running ingest scripts:
    python -m scripts.freeze_test_db
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DB = PROJECT_ROOT / "tests" / "fixtures" / "kisansaarthi_test.db"
LIVE_DB = PROJECT_ROOT / "kisansaarthi.db"

_TMP_DIR = Path(tempfile.mkdtemp(prefix="kisansaarthi_test_"))
TEST_DB = _TMP_DIR / "test.db"

if FIXTURE_DB.exists():
    TEST_DB_SOURCE = FIXTURE_DB
elif LIVE_DB.exists():
    TEST_DB_SOURCE = LIVE_DB
else:
    TEST_DB_SOURCE = None

if TEST_DB_SOURCE is not None:
    shutil.copy2(TEST_DB_SOURCE, TEST_DB)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

# Make sure every table exists even when no source DB was available.
import app.models  # noqa: E402,F401
import app.models_crop_soil  # noqa: E402,F401
import app.models_growth_stage  # noqa: E402,F401
import app.models_resistance  # noqa: E402,F401
import app.models_treatment_history  # noqa: E402,F401
from app.db import Base as _Base, engine as _engine  # noqa: E402

_Base.metadata.create_all(bind=_engine)


def pytest_report_header(config):
    source = TEST_DB_SOURCE.name if TEST_DB_SOURCE else "EMPTY (no fixture or live DB)"
    return f"test database: copy of {source}"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db():
    yield
    try:
        from app.db import engine

        engine.dispose()
    except Exception:
        pass
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


# ---------------------------------------------------------------------
# Tests that need your real data (registry CSV, coverage JSON, populated
# database). They are skipped with an explicit reason when that data is
# not in the project, and run normally once it is. Nothing is faked.
# ---------------------------------------------------------------------

import sqlite3  # noqa: E402


def _table_count(table: str) -> int:
    try:
        with sqlite3.connect(TEST_DB) as conn:
            return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    except sqlite3.Error:
        return 0


def _needs():
    registry_csv = PROJECT_ROOT / "data" / "registry" / "crop_registry_15.csv"
    coverage_json = PROJECT_ROOT / "data" / "coverage" / "crop_coverage.json"
    hint = "run scripts/import_local_assets.ps1 -Source C:\\farmer"
    return {
        "test_crop_registry_15.py": (registry_csv.exists(), f"data/registry/crop_registry_15.csv missing; {hint}"),
        "test_crop_coverage_service.py": (coverage_json.exists(), f"data/coverage/crop_coverage.json missing; {hint}"),
        "test_treatment_history_service.py": (
            _table_count("treatment_history_rules") > 0,
            f"treatment_history_rules table is empty; {hint}",
        ),
        "test_advisory_growth_stage_integration.py": (
            _table_count("registry_entries") > 0 and _table_count("growth_stage_rules") > 0,
            f"registry/growth-stage tables are empty; {hint}",
        ),
    }


def pytest_collection_modifyitems(config, items):
    needs = _needs()
    for item in items:
        name = Path(str(item.fspath)).name
        if name in needs:
            available, reason = needs[name]
            if not available:
                item.add_marker(pytest.mark.skip(reason=reason))
