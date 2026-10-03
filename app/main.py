from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models import DataProvenance

# Register models with SQLAlchemy
from app.models_treatment_history import TreatmentHistoryRule
from app.models_resistance import ResistanceRule

from app.routers.agent import router as agent_router

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
# This makes the project portable.
#
# Example:
# C:\MTech_Project\KisanSaarthi-AI\app\main.py
#
# Path(__file__)             -> app\main.py
# .resolve().parent          -> app
# .parent                    -> KisanSaarthi-AI
#
# Therefore there is NO hard-coded C:\farmer path.
# ============================================================

APP_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = APP_DIR.parent

FRONTEND_DIR = PROJECT_ROOT / "frontend"

INDEX_FILE = FRONTEND_DIR / "index.html"


# ============================================================
# FRONTEND VALIDATION
# ============================================================

if not FRONTEND_DIR.exists():
    raise RuntimeError(
        f"Frontend directory not found: {FRONTEND_DIR}"
    )

if not INDEX_FILE.exists():
    raise RuntimeError(
        f"Frontend index file not found: {INDEX_FILE}"
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
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():

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
# DEBUG FRONTEND
# ============================================================

@app.get("/debug/frontend")
def debug_frontend():

    text = INDEX_FILE.read_text(
        encoding="utf-8"
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
# FRONTEND HOME
# ============================================================

@app.get("/")
def home():

    return FileResponse(
        path=str(INDEX_FILE),

        media_type="text/html",

        headers={
            "Cache-Control":
                "no-store, no-cache, must-revalidate, max-age=0",

            "Pragma":
                "no-cache",

            "Expires":
                "0",
        },
    )