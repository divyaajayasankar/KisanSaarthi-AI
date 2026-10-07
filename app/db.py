from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def engine_options(url: str) -> dict:
    """SQLite needs check_same_thread=False for FastAPI's thread pool.
    Other databases (PostgreSQL via DATABASE_URL) take no such argument and
    get connection health checks instead."""
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, **engine_options(settings.database_url))


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
