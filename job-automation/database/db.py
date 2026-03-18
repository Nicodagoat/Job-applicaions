"""
Database connection, session management, and migration.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import yaml

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
with open(_SETTINGS_PATH) as _f:
    _SETTINGS = yaml.safe_load(_f)

DB_TYPE     = _SETTINGS["database"]["type"]
SQLITE_PATH = Path(__file__).parent.parent / _SETTINGS["database"]["sqlite_path"]


def _get_connection() -> sqlite3.Connection:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    """Create tables and run any pending migrations."""
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path) as f:
        schema_sql = f.read()
    with get_db() as conn:
        conn.executescript(schema_sql)
        conn.commit()
    _run_migrations()
    print("[DB] Database initialised.")


def _run_migrations() -> None:
    """Add new columns to existing databases without breaking them."""
    migrations = [
        # v2 — job validation fields
        "ALTER TABLE job_listings ADD COLUMN is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE job_listings ADD COLUMN verified_at TEXT",
        "ALTER TABLE job_listings ADD COLUMN closed_reason TEXT",
    ]
    with get_db() as conn:
        for sql in migrations:
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists — normal on fresh installs


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = _get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def rows_to_list(rows) -> list[dict]:
    return [row_to_dict(r) for r in rows]
