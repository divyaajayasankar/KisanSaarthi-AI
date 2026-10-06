"""Print what this installation has and what it is missing.

    python -m scripts.check_install

Read-only. Exit code is always 0; it reports, it does not block.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
CROPS = [
    "rice", "wheat", "maize", "tomato", "chilli", "brinjal", "onion", "potato",
    "okra", "cabbage", "groundnut", "chickpea", "mustard", "cotton", "banana",
]


def line(level: str, text: str) -> None:
    print(f"  [{level}] {text}")


def main() -> None:
    from sqlalchemy import func

    from app.config import settings
    from app.db import Base, SessionLocal, engine
    import app.models_conversation  # noqa: F401
    import app.models_crop_soil  # noqa: F401
    import app.models_growth_stage  # noqa: F401
    import app.models_resistance  # noqa: F401
    import app.models_treatment_history  # noqa: F401
    from app.models import RegistryEntry
    from app.services.speech_service import speech_available
    from app.services.vision_inference_service import supported_crops, torch_available

    Base.metadata.create_all(bind=engine)

    print("Installation check")

    with SessionLocal() as db:
        rows = (
            db.query(RegistryEntry.crop, func.count(RegistryEntry.id))
            .filter(RegistryEntry.verified.is_(True))
            .filter(RegistryEntry.is_test_data.is_(False))
            .group_by(RegistryEntry.crop)
            .all()
        )
    registry_crops = {crop.lower() for crop, _ in rows}
    total = sum(count for _, count in rows)
    if total == 0:
        line("WARN", "Verified registry is empty: every advisory will stop at 'no registered product'. "
                     "Run scripts\\import_local_assets.ps1 -Source C:\\farmer")
    else:
        missing = [c for c in CROPS if c not in registry_crops]
        extra = sorted(registry_crops - set(CROPS))
        covered = len(set(CROPS) & registry_crops)
        line("OK", f"Verified registry: {total} rows, {covered} of 15 crops covered")
        if missing:
            line("WARN", "No registry rows for: " + ", ".join(missing))
        if extra:
            line("WARN", "Registry crop names outside the 15-crop list (spelling or extra crop): " + ", ".join(extra))

    eval_dir = PROJECT_ROOT / "data" / "real_field_eval"
    counts = {}
    for crop in CROPS:
        folder = eval_dir / crop
        counts[crop] = sum(1 for p in folder.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES) if folder.exists() else 0
    images = sum(counts.values())
    level = "OK" if images >= 75 else "WARN"
    line(level, f"Real-field evaluation images: {images} of 75")

    line("OK" if (PROJECT_ROOT / "frontend" / "index.html").exists() else "INFO",
         "Classic form UI (/classic) " + ("present" if (PROJECT_ROOT / "frontend" / "index.html").exists()
                                         else "not installed (optional); import_local_assets.ps1 copies it"))

    key = bool(os.getenv("OPENWEATHER_API_KEY"))
    line("OK" if key else "WARN", "OPENWEATHER_API_KEY " + ("set" if key else
         "is empty: place lookup and weather checks will fail, so advisories stop at 'weather could not be verified'"))

    llm = settings.llm_active
    line("OK", "LLM mode " + ("A (LLM configured)" if llm else "B (deterministic, no LLM key needed)"))

    line("OK" if speech_available() else "WARN",
         "faster-whisper " + ("installed" if speech_available() else "NOT installed: voice input unavailable")
         + f" (model '{settings.whisper_model}' downloads on first use)")

    validated = supported_crops()
    if validated:
        line("OK", "Validated image models: " + ", ".join(validated))
    else:
        line("INFO", "No validated image model yet: image analysis abstains for every crop "
                     "(torch " + ("available" if torch_available() else "not installed; see requirements-vision.txt") + ")")


if __name__ == "__main__":
    main()
