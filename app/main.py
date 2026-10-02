from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models import DataProvenance

# Register Phase 7 model with SQLAlchemy
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
# ABSOLUTE FRONTEND PATH
# ============================================================

PROJECT_ROOT = Path(r"C:\farmer")

FRONTEND_DIR = (
    PROJECT_ROOT
    / "frontend"
)

INDEX_FILE = (
    FRONTEND_DIR
    / "index.html"
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=str(
            FRONTEND_DIR
        )
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
app.include_router(rag.router)

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
app.include_router(agent_router)

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
        "frontend_directory":
            str(FRONTEND_DIR),

        "index_file":
            str(INDEX_FILE),

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
        path=str(
            INDEX_FILE
        ),

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