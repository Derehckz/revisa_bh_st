"""Conexión y sesión SQLAlchemy para PostgreSQL."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

import settings


def _get_db_setting(key: str, default: str) -> str:
    """Prioriza BH_DB_* para evitar conflictos con variables globales del sistema."""
    return settings.get_setting(f"BH_DB_{key}", settings.get_setting(f"DB_{key}", default))


def get_database_url() -> str:
    host = _get_db_setting("HOST", "localhost")
    port = _get_db_setting("PORT", "5432")
    name = _get_db_setting("NAME", "boletas_honorarios")
    user = _get_db_setting("USER", "boletas_app")
    password = _get_db_setting("PASSWORD", "")
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=host,
        port=int(port),
        database=name,
    ).render_as_string(hide_password=False)


engine = create_engine(get_database_url(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
