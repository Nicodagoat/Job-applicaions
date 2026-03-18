"""
Smart CV selector.

When you upload multiple CV versions, this service automatically chooses
the best one for each job based on keyword overlap between the CV's tags
and the job description.

Example CV tags you can set when uploading:
  "esg, csrd, sustainability reporting"
  "policy, eu institutions, research"
  "consulting, stakeholder engagement"
  "general"   ← fallback/default
"""

from __future__ import annotations

import json
import re
from typing import Optional

from database.db import get_db, rows_to_list


# Keywords that indicate strong ESG/reporting focus
ESG_REPORTING_KEYWORDS = [
    "csrd", "eu taxonomy", "esg reporting", "disclosure", "sustainability report",
    "double materiality", "issb", "tcfd", "ghg", "scope 1", "scope 2", "scope 3",
    "carbon accounting", "emissions", "audit",
]

# Keywords that indicate policy/research focus
POLICY_KEYWORDS = [
    "policy", "regulation", "eu institutions", "legislation", "research",
    "think tank", "advocacy", "briefing", "analysis", "government",
    "public sector", "parliament", "commission",
]

# Keywords that indicate consulting focus
CONSULTING_KEYWORDS = [
    "consulting", "advisory", "client", "project management", "strategy",
    "engagement", "stakeholder", "deliver", "implementation",
]


def select_best_cv(
    job_title: str,
    job_description: str,
    requirements: Optional[list[str]] = None,
) -> Optional[dict]:
    """
    Select the most appropriate CV from stored documents for a given job.

    Returns the document dict of the best CV, or None if no CVs uploaded.

    Selection logic:
    1. Score each CV's tags against the job text
    2. Return highest scoring CV
    3. If tie → return the one marked is_default=True
    4. If nothing → return most recently uploaded CV
    """
    resumes = _get_all_resumes()
    if not resumes:
        return None
    if len(resumes) == 1:
        return resumes[0]

    job_text = (job_title + " " + job_description + " " + " ".join(requirements or [])).lower()
    job_profile = _classify_job(job_text)

    scored = []
    for cv in resumes:
        score = _score_cv_for_job(cv, job_text, job_profile)
        scored.append((score, cv))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_cv = scored[0]

    # Log the selection for transparency
    import logging
    logging.getLogger(__name__).info(
        f"[CVSelector] Selected CV '{best_cv['file_name']}' "
        f"(score={best_score:.1f}) for '{job_title}'"
    )
    return best_cv


def _get_all_resumes() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE doc_type = 'resume' ORDER BY is_default DESC, created_at DESC"
        ).fetchall()
        return rows_to_list(rows)


def _classify_job(job_text: str) -> dict:
    """Determine what type of role this is."""
    return {
        "esg_reporting": sum(1 for kw in ESG_REPORTING_KEYWORDS if kw in job_text),
        "policy":        sum(1 for kw in POLICY_KEYWORDS if kw in job_text),
        "consulting":    sum(1 for kw in CONSULTING_KEYWORDS if kw in job_text),
    }


def _score_cv_for_job(cv: dict, job_text: str, job_profile: dict) -> float:
    """
    Score a CV's suitability for a job.
    Uses CV description/tags and its filename as signals.
    """
    score = 0.0

    # Base score: default CV gets a small boost
    if cv.get("is_default"):
        score += 5.0

    # Parse CV tags from description
    cv_tags_raw = (cv.get("description") or cv.get("version") or cv.get("file_name") or "").lower()
    cv_tags = set(re.split(r"[,\s/|]+", cv_tags_raw))

    # Score tag overlap with job profile
    if any(kw in cv_tags_raw for kw in ESG_REPORTING_KEYWORDS):
        score += job_profile["esg_reporting"] * 3
    if any(kw in cv_tags_raw for kw in POLICY_KEYWORDS):
        score += job_profile["policy"] * 3
    if any(kw in cv_tags_raw for kw in CONSULTING_KEYWORDS):
        score += job_profile["consulting"] * 3

    # Generic/general CV works for everything but at half the score
    if "general" in cv_tags_raw or not cv.get("description"):
        score += 2.0

    return score


def get_cv_recommendation(job_title: str, job_description: str) -> dict:
    """
    Return a human-readable recommendation explaining which CV was chosen and why.
    Used by the frontend to show the user the selection rationale.
    """
    resumes = _get_all_resumes()
    if not resumes:
        return {"cv": None, "reason": "No CVs uploaded yet. Please upload at least one CV."}

    job_text = (job_title + " " + job_description).lower()
    job_profile = _classify_job(job_text)
    dominant = max(job_profile, key=job_profile.get)
    dominant_score = job_profile[dominant]

    best = select_best_cv(job_title, job_description)

    reasons = []
    if dominant_score >= 3:
        label = {"esg_reporting": "ESG reporting", "policy": "policy/research",
                 "consulting": "consulting"}.get(dominant, dominant)
        reasons.append(f"Job is primarily {label}-focused")
    if best and best.get("description"):
        reasons.append(f"CV tagged as: {best['description']}")
    if not reasons:
        reasons.append("Using default/most recent CV")

    return {
        "cv": best,
        "reason": " · ".join(reasons),
        "job_profile": job_profile,
        "total_cvs": len(resumes),
    }
