from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models import DataProvenance

# Register models with SQLAlchemy
from app.models_treatment_history import TreatmentHistoryRule
from app.models_resistance import ResistanceRule
from app.models_conversation import ConversationSession  # noqa: F401
import app.models_crop_soil  # noqa: F401
import app.models_growth_stage  # noqa: F401
import app.models_trace  # noqa: F401
from app.logging_config import configure_logging

from app.routers.agent import router as agent_router
from app.routers.vision import router as vision_router
from app.routers.chat import router as chat_router
from app.routers.speech import router as speech_router
from app.routers.whatsapp import router as whatsapp_router

from app.routers import (
    farmers,
    advisory,
    registry,
    weather,
    soil,
    crop_soil_rules,
    rag,
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title=settings.app_name
)


# ============================================================
# PROJECT PATHS
# ============================================================
# Portable project paths.
#
# Example company laptop:
# C:\farmer\app\main.py
#
# Path(__file__)             -> app\main.py
# .resolve().parent          -> app
# .parent                    -> project root
#
# No hard-coded project directory is required.
# ============================================================

APP_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = APP_DIR.parent

FRONTEND_DIR = PROJECT_ROOT / "frontend"

INDEX_FILE = FRONTEND_DIR / "index.html"

# Chat-style UI (main application).
CHAT_INDEX_FILE = FRONTEND_DIR / "chat" / "index.html"

# The original form UI stays at frontend/index.html and is served at
# /classic. It is optional so the chat app still starts if it is absent.


# ============================================================
# FRONTEND VALIDATION
# ============================================================

if not FRONTEND_DIR.exists():
    raise RuntimeError(
        f"Frontend directory not found: {FRONTEND_DIR}"
    )

if not CHAT_INDEX_FILE.exists():
    raise RuntimeError(
        f"Chat frontend not found: {CHAT_INDEX_FILE}"
    )


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(FRONTEND_DIR)
    ),
    name="static",
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    farmers.router
)

app.include_router(
    advisory.router
)

app.include_router(
    rag.router
)

app.include_router(
    registry.router
)

app.include_router(
    weather.router
)

app.include_router(
    soil.router
)

app.include_router(
    crop_soil_rules.router
)

app.include_router(
    agent_router
)


# ============================================================
# PHASE 1 â€” MULTIMODAL IMAGE ROUTER
# ============================================================
# Handles secure image upload and validation only.
#
# Endpoint:
# POST /api/vision/upload
#
# Upload validation only. Disease analysis is the separate
# POST /api/vision/analyze endpoint (vision_inference_service).
# ============================================================

app.include_router(
    vision_router
)


# ============================================================
# CONVERSATIONAL AGENT + VOICE
# ============================================================
# POST /api/chat/message       JSON text / coordinates
# POST /api/chat/turn          multipart text + image + coordinates
# POST /api/speech/transcribe  audio -> transcript (farmer confirms)
# GET/POST /api/whatsapp/webhook  WhatsApp Cloud API adapter
# POST /api/vision/analyze     crop-aware disease analysis
# ============================================================

app.include_router(
    chat_router
)

app.include_router(
    speech_router
)

app.include_router(
    whatsapp_router
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():

    configure_logging()

    Base.metadata.create_all(
        bind=engine
    )

    with SessionLocal() as db:

        unverified = (
            db.execute(
                select(
                    DataProvenance
                ).where(
                    DataProvenance
                    .verified
                    .is_(False)
                )
            )
            .scalars()
            .all()
        )

        if unverified:

            print(
                "WARNING: one or more data artifacts are unverified."
            )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "app": settings.app_name,
    }


# ============================================================
# STATUS (what data and engines are present in this install)
# ============================================================

@app.get("/api/status")
def status():

    from sqlalchemy import func

    from app.models import RegistryEntry
    from app.services.speech_service import speech_available
    from app.services.vision_inference_service import (
        supported_crops,
        torch_available,
    )

    eval_dir = PROJECT_ROOT / "data" / "real_field_eval"
    eval_images = 0

    if eval_dir.exists():
        eval_images = sum(
            1
            for path in eval_dir.rglob("*")
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )

    with SessionLocal() as db:
        registry_rows = (
            db.query(func.count(RegistryEntry.id))
            .filter(RegistryEntry.verified.is_(True))
            .filter(RegistryEntry.is_test_data.is_(False))
            .scalar()
        ) or 0

        registry_crops = sorted(
            row[0]
            for row in db.query(RegistryEntry.crop)
            .filter(RegistryEntry.verified.is_(True))
            .filter(RegistryEntry.is_test_data.is_(False))
            .distinct()
            .all()
        )

    return {
        "app": settings.app_name,
        "verified_registry_rows": registry_rows,
        "registry_crops": registry_crops,
        "classic_ui_present": INDEX_FILE.exists(),
        "real_field_eval_images": eval_images,
        "vision_runtime_available": torch_available(),
        "vision_validated_crops": supported_crops(),
        "speech_available": speech_available(),
        "whisper_model": settings.whisper_model,
        "llm_mode": "A" if settings.llm_active else "B",
        "weather_key_configured": bool(
            __import__("os").getenv("OPENWEATHER_API_KEY")
        ),
    }


# ============================================================
# DEBUG FRONTEND
# ============================================================

@app.get("/debug/frontend")
def debug_frontend():

    text = (
        INDEX_FILE.read_text(encoding="utf-8")
        if INDEX_FILE.exists()
        else ""
    )

    return {
        "project_root":
            str(PROJECT_ROOT),

        "frontend_directory":
            str(FRONTEND_DIR),

        "index_file":
            str(INDEX_FILE),

        "frontend_exists":
            FRONTEND_DIR.exists(),

        "index_exists":
            INDEX_FILE.exists(),

        "chat_index_exists":
            CHAT_INDEX_FILE.exists(),

        "has_growth_stage":
            "growthStage" in text,

        "has_phase7_heading":
            "Previous Treatment History"
            in text,

        "has_previous_application_count":
            "previousApplicationCount"
            in text,
    }


# ============================================================
# FRONTEND HOME (chat) AND CLASSIC FORM
# ============================================================

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/")
def home():

    return FileResponse(
        path=str(CHAT_INDEX_FILE),
        media_type="text/html",
        headers=NO_CACHE_HEADERS,
    )


@app.get("/classic")
def classic():

    if not INDEX_FILE.exists():
        return HTMLResponse(
            "<h3>Classic form UI not found.</h3>"
            "<p>Copy your original frontend/index.html, app.js and style.css "
            "into the frontend folder (scripts/import_local_assets.ps1 does this).</p>",
            status_code=404,
        )

    return FileResponse(
        path=str(INDEX_FILE),
        media_type="text/html",
        headers=NO_CACHE_HEADERS,
    )
