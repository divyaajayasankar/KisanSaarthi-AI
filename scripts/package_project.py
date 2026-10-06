"""Build Context_Aware_Crop_Advisory_Final.zip.

    python -m scripts.package_project
    python -m scripts.package_project --output D:\\drop\\final.zip --no-db

What goes in
    app/, frontend/, scripts/, tests/, data/ (reference data + the small
    curated data/real_field_eval set + metadata.csv), reports/ (if any),
    requirements*.txt, .env.example, pytest.ini, README.md,
    RUN_COMMANDS.txt, run_project.ps1, and a SANITIZED copy of
    kisansaarthi.db (reference tables only, personal tables emptied) when
    the live database exists.

What stays out
    .venv/venv, .git, caches, .env and any real secret, other *.db files
    and backups, raw source datasets, farmer uploads, trained weights not
    referenced by data/models/model_registry.json, superseded router and
    schema backups, existing *.zip files.

The script refuses to write the ZIP if it finds something that looks like
a credential, then re-opens the finished ZIP and verifies it.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from pathlib import Path

from scripts.freeze_test_db import PERSONAL_TABLES, snapshot  # noqa: F401  (PERSONAL_TABLES documents the policy)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_NAME = "Context_Aware_Crop_Advisory_Final"
DEFAULT_OUTPUT = PROJECT_ROOT / f"{ROOT_NAME}.zip"

EXCLUDE_DIRS = {".venv", "venv", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
EXCLUDE_TOP = {"data/uploads", "data/source_datasets", "data/real_field_eval/_invalid"}
EXCLUDE_NAME_PATTERNS = [
    r"^\.env$", r"^\.env\..+(?<!\.example)$", r".*\.pyc$", r".*\.zip$", r".*\.db$", r".*\.db-journal$",
    r".*\.db\.bak$", r".*\.bak$", r"^_backup_.*", r"^fix_frontend\.py$", r"^\.DS_Store$", r"^Thumbs\.db$",
    r"^advisory_before_.*\.py$", r"^advisory_phase\d+_complete\.py$", r"^schemas_before_.*\.py$",
    r"^pytest_.*\.txt$", r"^source_datasets_tree\.txt$",
]
SECRET_PATTERNS = [
    (re.compile(
        r"""(?im)^[ \t]*(?:export[ \t]+)?(?:OPENWEATHER_API_KEY|LLM_API_KEY|WHATSAPP_ACCESS_TOKEN)"""
        r"""[ \t]*=[ \t]*["']?[A-Za-z0-9_\-\.]{16,}["']?[ \t]*(?:#.*)?$"""
    ), "API key value assigned"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "API key (sk-...)"),
    (re.compile(r"(?i)[?&]appid=[0-9a-f]{24,}"), "OpenWeather key in a URL"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.]{30,}"), "bearer token"),
]
TEXT_SUFFIXES = {".py", ".txt", ".md", ".json", ".csv", ".ps1", ".html", ".js", ".css", ".ini", ".example", ".yml", ".yaml", ".toml", ""}
REQUIRED = [
    "README.md", "RUN_COMMANDS.txt", "run_project.ps1", "requirements.txt", ".env.example", "pytest.ini",
    "app/main.py", "frontend/chat/index.html", "scripts/evaluate_real_field.py",
    "scripts/evaluate_personalization.py", "tests/conftest.py", "data/registry/pest_aliases.csv",
    "data/i18n/lexicon.json", "data/i18n/messages.json",
]
FORBIDDEN_FILES = {".env"}
FORBIDDEN_DIRS = (".venv/", "venv/", ".git/", "__pycache__/", ".pytest_cache/")


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def excluded_by_name(name: str) -> bool:
    return any(re.match(pattern, name) for pattern in EXCLUDE_NAME_PATTERNS)


def referenced_model_files() -> set[str]:
    registry = PROJECT_ROOT / "data" / "models" / "model_registry.json"
    if not registry.exists():
        return set()
    entries = json.loads(registry.read_text(encoding="utf-8")).get("models", {})
    return {entry["path"] for entry in entries.values() if entry.get("path")}


def collect() -> list[Path]:
    keep_models = referenced_model_files()
    files: list[Path] = []
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if not path.is_file():
            continue
        parts = path.relative_to(PROJECT_ROOT).parts
        if any(part in EXCLUDE_DIRS for part in parts):
            continue
        name = rel(path)
        if any(name == top or name.startswith(top + "/") for top in EXCLUDE_TOP):
            continue
        if path.suffix == ".pt" and name not in keep_models:
            continue
        if path.name == "kisansaarthi_test.db" and "tests/fixtures" in name:
            files.append(path)  # sanitized fixture is intentionally shipped
            continue
        if excluded_by_name(path.name):
            continue
        files.append(path)
    return files


def scan_for_secrets(files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{rel(path)}: {label}")
    return findings


def build(output: Path, include_db: bool) -> dict:
    files = collect()
    findings = scan_for_secrets(files)
    if findings:
        raise SystemExit("Refusing to package. Possible secrets found:\n  " + "\n  ".join(findings))

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    live_db = PROJECT_ROOT / "kisansaarthi.db"
    db_note = "no live database found; none included"

    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, f"{ROOT_NAME}/{rel(path)}")

        if include_db and live_db.exists():
            clean = Path(tmp) / "kisansaarthi.db"
            counts = snapshot(live_db, clean)
            archive.write(clean, f"{ROOT_NAME}/kisansaarthi.db")
            db_note = "sanitized kisansaarthi.db included: " + ", ".join(f"{t}={n}" for t, n in counts.items() if n)
        elif live_db.exists():
            db_note = "live database present but --no-db given; not included"

    return {"files": len(files), "db": db_note, "output": output}


def verify(output: Path) -> list[str]:
    problems: list[str] = []
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        short = {name.split("/", 1)[1] for name in names if "/" in name}
        for required in REQUIRED:
            if required not in short:
                problems.append(f"missing required file: {required}")
        for name in sorted(short):
            parts = name.split("/")
            if parts[-1] in FORBIDDEN_FILES:
                problems.append(f"forbidden file in ZIP: {name}")
            if any(f"{part}/" in FORBIDDEN_DIRS for part in parts[:-1]):
                problems.append(f"forbidden folder in ZIP: {name}")
        if archive.testzip() is not None:
            problems.append("ZIP failed its integrity test")
        env_example = archive.read(f"{ROOT_NAME}/.env.example").decode("utf-8", errors="ignore")
        if re.search(r"(?im)^(OPENWEATHER_API_KEY|LLM_API_KEY)=\S", env_example):
            problems.append(".env.example contains a value")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--no-db", action="store_true", help="do not include the sanitized database")
    args = parser.parse_args()

    result = build(Path(args.output), include_db=not args.no_db)
    problems = verify(result["output"])

    eval_dir = PROJECT_ROOT / "data" / "real_field_eval"
    images = sum(
        1 for p in eval_dir.glob("*/*")
        if p.is_file() and not p.parent.name.startswith("_") and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ) if eval_dir.exists() else 0
    size_mb = result["output"].stat().st_size / (1024 * 1024)

    print(f"ZIP: {result['output']}  ({size_mb:.1f} MB, {result['files']} files)")
    print(f"Evaluation images included: {images} of 75" + ("" if images >= 75 else "  (dataset NOT complete)"))
    print(f"Database: {result['db']}")
    if (PROJECT_ROOT / "data" / "real_field_eval" / "metadata.csv").exists():
        print("metadata.csv: included")
    else:
        print("metadata.csv: MISSING (run python -m scripts.build_eval_metadata)")
    if problems:
        print("\nVERIFICATION FAILED:")
        for problem in problems:
            print("  -", problem)
        raise SystemExit(1)
    print("Verification passed: required files present, no secrets, no .env/.venv/.git/caches.")


if __name__ == "__main__":
    main()
