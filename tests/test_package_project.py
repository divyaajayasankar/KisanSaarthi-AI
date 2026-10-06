"""The packager must keep secrets, personal data and bulk data out of the ZIP."""

import sqlite3
import zipfile

import pytest

from scripts import package_project as pp


REQUIRED_FILES = pp.REQUIRED


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    for name in REQUIRED_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    (root / ".env.example").write_text("OPENWEATHER_API_KEY=\nLLM_API_KEY=\nDATABASE_URL=sqlite:///./kisansaarthi.db\n", encoding="utf-8")

    junk = {
        ".env": "OPENWEATHER_API_KEY=" + "0123456789abcdef" + "0123456789abcdef" + "\n",
        ".venv/lib/x.py": "x",
        "app/__pycache__/a.pyc": "x",
        ".git/config": "x",
        "data/source_datasets/Huge/raw.jpg": "x",
        "data/uploads/s1/farmer.jpg": "x",
        "app/routers/advisory_before_weather.py": "x",
        "app/schemas_before_soil_integration.py": "x",
        "kisansaarthi_20260901.db": "x",
        "other.db": "x",
        "old.zip": "x",
        "pytest_baseline.txt": "x",
        "data/models/orphan.pt": "x",
        "data/models/used.pt": "weights",
        "data/real_field_eval/rice/rice_blast_01.jpg": "img",
        "data/real_field_eval/metadata.csv": "crop,disease,filename,source,dataset,license\n",
    }
    for name, content in junk.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (root / "data/models/model_registry.json").write_text('{"models": {"rice": {"path": "data/models/used.pt"}}}', encoding="utf-8")

    with sqlite3.connect(root / "kisansaarthi.db") as conn:
        conn.execute("CREATE TABLE registry_entries (id INTEGER PRIMARY KEY, crop TEXT)")
        conn.execute("CREATE TABLE farmer_profiles (id INTEGER PRIMARY KEY, farmer_name TEXT)")
        conn.execute("INSERT INTO registry_entries (crop) VALUES ('Rice')")
        conn.execute("INSERT INTO farmer_profiles (farmer_name) VALUES ('Real Farmer')")

    monkeypatch.setattr(pp, "PROJECT_ROOT", root)
    return root


def build(project, tmp_path, include_db=True):
    output = tmp_path / "out.zip"
    result = pp.build(output, include_db=include_db)
    with zipfile.ZipFile(output) as archive:
        names = {n.split("/", 1)[1] for n in archive.namelist() if "/" in n}
    return output, names, result


def test_secrets_bulk_data_and_backups_are_excluded(project, tmp_path):
    _, names, _ = build(project, tmp_path)
    assert ".env" not in names
    for excluded in (
        ".venv/lib/x.py", "app/__pycache__/a.pyc", ".git/config", "data/source_datasets/Huge/raw.jpg",
        "data/uploads/s1/farmer.jpg", "app/routers/advisory_before_weather.py",
        "app/schemas_before_soil_integration.py", "kisansaarthi_20260901.db", "other.db", "old.zip",
        "pytest_baseline.txt", "data/models/orphan.pt",
    ):
        assert excluded not in names, excluded


def test_required_and_evaluation_files_are_included(project, tmp_path):
    _, names, _ = build(project, tmp_path)
    for required in REQUIRED_FILES:
        assert required in names
    assert ".env.example" in names
    assert "data/real_field_eval/rice/rice_blast_01.jpg" in names
    assert "data/real_field_eval/metadata.csv" in names
    assert "data/models/used.pt" in names          # referenced by model_registry.json


def test_shipped_database_is_sanitized_and_live_one_untouched(project, tmp_path):
    output, names, _ = build(project, tmp_path)
    assert "kisansaarthi.db" in names
    extract = tmp_path / "x"
    with zipfile.ZipFile(output) as archive:
        archive.extract(f"{pp.ROOT_NAME}/kisansaarthi.db", extract)
    shipped = sqlite3.connect(extract / pp.ROOT_NAME / "kisansaarthi.db")
    assert shipped.execute("SELECT COUNT(*) FROM registry_entries").fetchone()[0] == 1
    assert shipped.execute("SELECT COUNT(*) FROM farmer_profiles").fetchone()[0] == 0
    live = sqlite3.connect(project / "kisansaarthi.db")
    assert live.execute("SELECT COUNT(*) FROM farmer_profiles").fetchone()[0] == 1


def test_no_db_flag_leaves_database_out(project, tmp_path):
    _, names, _ = build(project, tmp_path, include_db=False)
    assert "kisansaarthi.db" not in names


def test_packaging_refuses_when_a_key_is_present(project, tmp_path):
    (project / "app" / "config_notes.py").write_text('LLM_API_KEY = "' + "sk" + "-abcdefghijklmnopqrstuvwxyz0123" + '"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as raised:
        pp.build(tmp_path / "refused.zip", include_db=False)
    assert "Possible secrets" in str(raised.value)
    assert not (tmp_path / "refused.zip").exists()


def test_reading_a_key_from_the_environment_is_not_a_secret(project, tmp_path):
    (project / "app" / "reader.py").write_text('OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")\n', encoding="utf-8")
    output, _, _ = build(project, tmp_path, include_db=False)
    assert output.exists()


def test_verify_passes_on_a_good_zip_and_flags_a_missing_file(project, tmp_path):
    output, _, _ = build(project, tmp_path)
    assert pp.verify(output) == []

    (project / "README.md").unlink()
    broken = tmp_path / "broken.zip"
    pp.build(broken, include_db=False)
    assert any("README.md" in problem for problem in pp.verify(broken))
