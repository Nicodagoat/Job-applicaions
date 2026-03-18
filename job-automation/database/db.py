"""
Database connection and session management.
Supports SQLite (default) and PostgreSQL.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import yaml

# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

def _load_settings() -> dict:
    settings_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(settings_path) as f:
        return yaml.safe_load(f)


SETTINGS = _load_settings()
DB_TYPE = SETTINGS["database"]["type"]
SQLITE_PATH = Path(__file__).parent.parent / SETTINGS["database"]["sqlite_path"]


# --------------------------------------------------------------------------- #
# SQLite                                                                       #
# --------------------------------------------------------------------------- #

def _get_sqlite_connection() -> sqlite3.Connection:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    """Create all tables from schema.sql if they don't exist."""
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path) as f:
        schema_sql = f.read()

    with get_db() as conn:
        conn.executescript(schema_sql)
        conn.commit()
    print("[DB] Database initialised.")


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a database connection."""
    if DB_TYPE == "sqlite":
        conn = _get_sqlite_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        raise NotImplementedError(
            "PostgreSQL support: install asyncpg and update this function."
        )


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def rows_to_list(rows) -> list[dict]:
    """Convert a list of sqlite3.Row objects to a list of dicts."""
    return [row_to_dict(r) for r in rows]
