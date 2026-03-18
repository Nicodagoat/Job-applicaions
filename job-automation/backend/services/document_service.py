"""
Document management service.
Handles upload, retrieval, and selection of application documents.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Optional

import yaml

from database.db import get_db, rows_to_list, row_to_dict


# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

_SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
with open(_SETTINGS_PATH) as _f:
    _SETTINGS = yaml.safe_load(_f)

STORAGE_ROOT = Path(__file__).parent.parent.parent / _SETTINGS["documents"]["storage_path"]
MAX_FILE_BYTES = _SETTINGS["documents"]["max_file_size_mb"] * 1024 * 1024
ALLOWED_EXTS = set(_SETTINGS["documents"]["allowed_extensions"])

# Subdirectory per document type
TYPE_DIRS = {
    "resume": "resumes",
    "cover_letter": "cover_letters",
    "certificate": "certificates",
    "transcript": "certificates",
    "portfolio": "other",
    "other": "other",
}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _ensure_dirs() -> None:
    for sub in TYPE_DIRS.values():
        (STORAGE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def _safe_filename(filename: str) -> str:
    """Return a filename safe for the OS."""
    return "".join(c if (c.isalnum() or c in "._- ") else "_" for c in filename)


# --------------------------------------------------------------------------- #
# CRUD                                                                         #
# --------------------------------------------------------------------------- #

def save_document(
    file_bytes: bytes,
    original_filename: str,
    doc_type: str,
    version: Optional[str] = None,
    description: Optional[str] = None,
    is_default: bool = False,
    created_for: Optional[int] = None,
) -> dict:
    """
    Persist a document to disk and register it in the database.
    Returns the created document record.
    """
    _ensure_dirs()

    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"File type {ext} is not allowed. Allowed: {ALLOWED_EXTS}")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds maximum size of {_SETTINGS['documents']['max_file_size_mb']} MB")

    # Build storage path
    safe_name = _safe_filename(original_filename)
    sub_dir = TYPE_DIRS.get(doc_type, "other")
    dest_dir = STORAGE_ROOT / sub_dir
    dest_path = dest_dir / safe_name

    # Avoid name collisions
    counter = 1
    while dest_path.exists():
        stem = Path(safe_name).stem
        dest_path = dest_dir / f"{stem}_{counter}{ext}"
        counter += 1

    dest_path.write_bytes(file_bytes)

    mime_type, _ = mimetypes.guess_type(str(dest_path))
    relative_path = str(dest_path.relative_to(STORAGE_ROOT.parent.parent))

    with get_db() as conn:
        # If setting as default, unset existing default
        if is_default:
            conn.execute(
                "UPDATE documents SET is_default = 0 WHERE doc_type = ? AND is_default = 1",
                (doc_type,),
            )
        cursor = conn.execute(
            """
            INSERT INTO documents
                (doc_type, file_name, file_path, version, description,
                 is_default, created_for, file_size, mime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_type,
                original_filename,
                relative_path,
                version,
                description,
                is_default,
                created_for,
                len(file_bytes),
                mime_type,
            ),
        )
        conn.commit()
        return get_document(cursor.lastrowid)


def get_document(doc_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return row_to_dict(row) if row else None


def list_documents(doc_type: Optional[str] = None) -> list[dict]:
    with get_db() as conn:
        if doc_type:
            rows = conn.execute(
                "SELECT * FROM documents WHERE doc_type = ? ORDER BY created_at DESC",
                (doc_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY doc_type, created_at DESC"
            ).fetchall()
        return rows_to_list(rows)


def get_default_resume() -> Optional[dict]:
    """Return the default resume document."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_type = 'resume' AND is_default = 1 LIMIT 1"
        ).fetchone()
        # Fallback: most recent resume
        if not row:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_type = 'resume' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return row_to_dict(row) if row else None


def delete_document(doc_id: int) -> bool:
    doc = get_document(doc_id)
    if not doc:
        return False
    try:
        Path(doc["file_path"]).unlink(missing_ok=True)
    except Exception:
        pass
    with get_db() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
    return True
