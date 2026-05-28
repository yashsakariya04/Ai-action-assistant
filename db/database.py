"""
db/database.py — SQLAlchemy engine + session factory.

Uses DATABASE_URL from env.
Falls back to SQLite for local dev if DATABASE_URL is not set.
"""

import os
import re
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from db.models import Base

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Railway injects postgres:// — SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fallback to SQLite for local dev
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./assistant.db"
    log.warning("DATABASE_URL not set — using SQLite (local dev only)")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Create all tables if they don't exist, and run lightweight column migrations."""
    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    log.info("Database tables ready.")


_VALID_TABLES = {"users", "sessions", "messages", "google_tokens"}
_VALID_TYPES  = {"VARCHAR(500)", "VARCHAR(300)", "TEXT", "BOOLEAN", "INTEGER"}


def _migrate_columns():
    """Add new columns to existing tables if they don't exist (SQLite + PostgreSQL safe)."""
    migrations = [
        ("users", "avatar_url", "VARCHAR(500)"),
        ("users", "bio",        "VARCHAR(300)"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            assert table in _VALID_TABLES, f"Unknown table: {table}"
            assert col_type in _VALID_TYPES, f"Unknown col type: {col_type}"
            assert re.fullmatch(r"[a-z_]{1,64}", column), f"Invalid column name: {column}"
            try:
                from sqlalchemy import text as _text
                conn.execute(_text(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                ))
                conn.commit()
                log.info("Migration: added column %s.%s", table, column)
            except Exception:
                pass  # Column already exists


def get_db() -> Session:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
