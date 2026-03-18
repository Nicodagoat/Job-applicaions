"""
Document management API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from backend.services.document_service import (
    delete_document,
    get_document,
    list_documents,
    save_document,
)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get("/")
def get_documents(doc_type: Optional[str] = None):
    return list_documents(doc_type=doc_type)


@router.get("/{doc_id}")
def get_document_detail(doc_id: int):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    version: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_default: bool = Form(False),
):
    file_bytes = await file.read()
    try:
        doc = save_document(
            file_bytes=file_bytes,
            original_filename=file.filename,
            doc_type=doc_type,
            version=version,
            description=description,
            is_default=is_default,
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{doc_id}/set-default")
def set_default_document(doc_id: int):
    """Mark a document as the default for its type (clears previous default)."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    from database.db import get_db
    with get_db() as conn:
        conn.execute(
            "UPDATE documents SET is_default=0 WHERE doc_type=? AND is_default=1",
            (doc["doc_type"],),
        )
        conn.execute("UPDATE documents SET is_default=1 WHERE id=?", (doc_id,))
        conn.commit()
    return get_document(doc_id)


@router.delete("/{doc_id}")
def remove_document(doc_id: int):
    if not delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}
