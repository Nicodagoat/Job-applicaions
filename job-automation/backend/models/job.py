"""
Pydantic models for job listings and applications.
Used for API request/response validation.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# --------------------------------------------------------------------------- #
# Job Listing                                                                  #
# --------------------------------------------------------------------------- #

class JobListingBase(BaseModel):
    job_title: str
    company: str
    location: Optional[str] = None
    country: Optional[str] = None
    remote: bool = False
    source: str
    source_url: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[list[str]] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "GBP"
    posted_date: Optional[str] = None
    deadline: Optional[str] = None
    esg_relevant: bool = False


class JobListingCreate(JobListingBase):
    external_id: Optional[str] = None
    raw_data: Optional[dict] = None


class JobListing(JobListingBase):
    id: int
    match_score: float = 0.0
    match_breakdown: Optional[dict] = None
    priority: str = "normal"
    discovered_at: str
    last_updated: str

    model_config = {"from_attributes": True}

    @field_validator("requirements", "match_breakdown", mode="before")
    @classmethod
    def parse_json_fields(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v


# --------------------------------------------------------------------------- #
# Application                                                                  #
# --------------------------------------------------------------------------- #

APPLICATION_STATUSES = [
    "pending",
    "approved",
    "submitted",
    "acknowledged",
    "interview_invited",
    "rejected",
    "withdrawn",
    "on_hold",
]


class ApplicationCreate(BaseModel):
    job_id: int
    notes: Optional[str] = None
    submission_method: Optional[str] = None


class ApplicationUpdate(BaseModel):
    application_status: Optional[str] = None
    notes: Optional[str] = None
    next_action_required: Optional[str] = None
    next_action_due: Optional[str] = None
    human_approved: Optional[bool] = None

    @field_validator("application_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v and v not in APPLICATION_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {APPLICATION_STATUSES}")
        return v


class Application(ApplicationCreate):
    id: int
    application_status: str = "pending"
    date_applied: Optional[str] = None
    form_url: Optional[str] = None
    confirmation_code: Optional[str] = None
    next_action_required: Optional[str] = None
    next_action_due: Optional[str] = None
    human_approved: bool = False
    approved_at: Optional[str] = None
    submitted_at: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Document                                                                     #
# --------------------------------------------------------------------------- #

DOCUMENT_TYPES = ["resume", "cover_letter", "certificate", "transcript", "portfolio", "other"]


class DocumentCreate(BaseModel):
    doc_type: str
    file_name: str
    file_path: str
    version: Optional[str] = None
    description: Optional[str] = None
    is_default: bool = False

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"doc_type must be one of: {DOCUMENT_TYPES}")
        return v


class Document(DocumentCreate):
    id: int
    created_for: Optional[int] = None
    created_at: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Cover Letter                                                                 #
# --------------------------------------------------------------------------- #

class CoverLetterCreate(BaseModel):
    job_id: int
    content: str
    ai_model: Optional[str] = None
    sources_used: Optional[list[str]] = None


class CoverLetter(CoverLetterCreate):
    id: int
    human_edited: bool = False
    approved: bool = False
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Pagination                                                                   #
# --------------------------------------------------------------------------- #

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
