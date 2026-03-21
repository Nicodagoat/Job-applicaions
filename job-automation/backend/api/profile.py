"""
Profile API — read and write the user's personal info (config/profile.yaml).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.profile_service import read_profile, update_profile_section

router = APIRouter(prefix="/api/profile", tags=["profile"])
logger = logging.getLogger(__name__)


class SectionPayload(BaseModel):
    data: Any


@router.get("")
def get_profile():
    """Return the full profile."""
    try:
        return read_profile()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{section}")
def save_section(section: str, payload: SectionPayload):
    """
    Save one section of the profile.
    section = personal | summary | languages | skills |
              work_experience | education | job_titles |
              keywords | locations | salary | seniority |
              visa | application
    """
    allowed = {
        "personal", "summary", "languages", "skills",
        "work_experience", "education", "job_titles",
        "keywords", "locations", "salary", "seniority",
        "visa", "application",
    }
    if section not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown section: {section}")
    try:
        update_profile_section(section, payload.data)
        return {"ok": True, "message": "Profile saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
