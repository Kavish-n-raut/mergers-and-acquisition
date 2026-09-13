from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _normalize_db_url(url: str) -> str:
    """Route Postgres URLs through the installed psycopg (v3) driver.

    Neon / Supabase / Heroku hand out `postgres://` or `postgresql://` URLs,
    which SQLAlchemy would otherwise try to open with psycopg2 (not installed).
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_db_url = _normalize_db_url(settings.database_url)
# SQLite needs check_same_thread=False for FastAPI's threaded request handling;
# Postgres needs no special connect args.
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(_db_url, future=True, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

