"""
Job matching engine.

Scores job listings against the candidate profile using a weighted rubric.
Does NOT use AI for scoring — purely rule-based to avoid hallucination.
AI is used only for initial requirement extraction.
"""

from __future__ import annotations

import re
from typing import Optional

import yaml
from pathlib import Path

from ai.profile_loader import PROFILE_FACTS, get_all_skills


# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #

_PROFILE_CFG_PATH = Path(__file__).parent.parent / "config" / "profile.yaml"
with open(_PROFILE_CFG_PATH) as _f:
    _PROFILE_CFG = yaml.safe_load(_f)

_WEIGHTS = _PROFILE_CFG["matching_weights"]
_PRIORITY_INDUSTRIES = [i.lower() for i in _PROFILE_CFG["industries"]["priority"]]
_PRIORITY_COMPANIES = [c.lower() for c in _PROFILE_CFG["companies"]["prioritize"]]
_EXCLUDED_INDUSTRIES = [i.lower() for i in _PROFILE_CFG["industries"]["avoid"]]
_TARGET_COUNTRIES = [c.lower() for c in _PROFILE_CFG["locations"]["target_countries"]]
_EXCLUDED_COUNTRIES = [c.lower() for c in _PROFILE_CFG["locations"]["excluded_countries"]]

# ESG / sustainability keywords that boost relevance
ESG_KEYWORDS = [
    "esg", "sustainability", "csrd", "eu taxonomy", "climate", "carbon",
    "ghg", "net zero", "green", "environmental", "tcfd", "issb",
    "double materiality", "scope 1", "scope 2", "scope 3",
    "circular economy", "biodiversity", "just transition",
    "renewable", "low carbon", "paris agreement", "cop", "sdg",
    "impact investing", "responsible investment", "sri",
    "climate policy", "environmental regulation", "eu green deal",
]

PROFILE_SKILLS_LOWER = [s.lower() for s in get_all_skills()]


# --------------------------------------------------------------------------- #
# Scoring                                                                      #
# --------------------------------------------------------------------------- #

class MatchingEngine:
    """
    Deterministic, rule-based job scoring.

    Score breakdown (0-100 each, weighted to produce overall 0-100):
      - skill_match       (30%)
      - location_match    (20%)
      - seniority_match   (15%)
      - industry_relevance(20%)
      - company_priority  (10%)
      - esg_relevance     (5%)
    """

    def score(
        self,
        job_title: str,
        company: str,
        location: str,
        country: Optional[str],
        description: str,
        requirements: Optional[list[str]] = None,
        remote: bool = False,
    ) -> dict:
        """
        Returns:
            {
                "overall_score": float (0-100),
                "breakdown": {
                    "skill_match": ..., "location_match": ..., ...
                },
                "matched_skills": list,
                "missing_skills": list,
                "flags": list,     # Issues that might prevent application
                "esg_relevant": bool,
            }
        """
        flags = []

        # --- 1. Location check (hard exclusions) ---
        location_score, location_flag = self._score_location(country, location, remote)
        if location_flag:
            flags.append(location_flag)

        # --- 2. Industry / company exclusions ---
        if self._is_excluded_industry(description, job_title):
            flags.append("Job appears to be in an excluded industry.")
            return self._zero_score("Excluded industry", flags)

        # --- 3. Compute sub-scores ---
        skill_score, matched, missing = self._score_skills(description, requirements)
        seniority_score = self._score_seniority(job_title, description)
        industry_score = self._score_industry(description, job_title)
        company_score = self._score_company(company)
        esg_score, esg_relevant = self._score_esg(description, job_title)

        # --- 4. Weighted overall ---
        overall = (
            skill_score    * _WEIGHTS["skill_match"] +
            location_score * _WEIGHTS["location_match"] +
            seniority_score * _WEIGHTS["seniority_match"] +
            industry_score * _WEIGHTS["industry_relevance"] +
            company_score  * _WEIGHTS["company_priority"] +
            esg_score      * _WEIGHTS["esg_relevance"]
        )

        return {
            "overall_score": round(overall, 1),
            "breakdown": {
                "skill_match": skill_score,
                "location_match": location_score,
                "seniority_match": seniority_score,
                "industry_relevance": industry_score,
                "company_priority": company_score,
                "esg_relevance": esg_score,
            },
            "matched_skills": matched,
            "missing_skills": missing,
            "flags": flags,
            "esg_relevant": esg_relevant,
        }

    # ---------------------------------------------------------------------- #

    def _score_skills(
        self, description: str, requirements: Optional[list[str]]
    ) -> tuple[float, list[str], list[str]]:
        text = (description + " " + " ".join(requirements or [])).lower()
        matched, missing = [], []
        for skill in PROFILE_SKILLS_LOWER:
            if skill in text:
                matched.append(skill)
        # Count unmatched requirements
        for req in (requirements or []):
            req_lower = req.lower()
            if not any(s in req_lower for s in PROFILE_SKILLS_LOWER):
                missing.append(req)
        score = min(100, (len(matched) / max(len(PROFILE_SKILLS_LOWER), 1)) * 300)
        return round(score, 1), matched, missing[:5]  # Cap missing list

    def _score_location(
        self, country: Optional[str], location: str, remote: bool
    ) -> tuple[float, Optional[str]]:
        if remote:
            return 80.0, None  # Remote is acceptable

        loc_text = ((country or "") + " " + (location or "")).lower()

        for excl in _EXCLUDED_COUNTRIES:
            if excl in loc_text:
                return 0.0, f"Location '{location}' is in excluded country ({excl})."

        for target in _TARGET_COUNTRIES:
            if target in loc_text:
                return 100.0, None

        # Unknown location — don't block, but reduce score
        return 50.0, None

    def _score_seniority(self, job_title: str, description: str) -> float:
        text = (job_title + " " + description).lower()
        if any(w in text for w in ["director", "vp ", "vice president", "partner", "head of"]):
            return 30.0  # Too senior
        if any(w in text for w in ["intern", "graduate scheme", "entry level", "trainee"]):
            return 50.0  # Slightly below target
        if any(w in text for w in ["senior", "lead", "principal", "manager"]):
            return 85.0  # Good fit
        if any(w in text for w in ["junior", "associate", "analyst"]):
            return 75.0  # Acceptable
        return 70.0  # Neutral

    def _score_industry(self, description: str, job_title: str) -> float:
        text = (description + " " + job_title).lower()
        # Priority industry match
        for industry in _PRIORITY_INDUSTRIES:
            if any(word in text for word in industry.split()):
                return 100.0
        return 50.0

    def _score_company(self, company: str) -> float:
        company_lower = company.lower()
        for priority_co in _PRIORITY_COMPANIES:
            if priority_co in company_lower or company_lower in priority_co:
                return 100.0
        return 50.0

    def _score_esg(self, description: str, job_title: str) -> tuple[float, bool]:
        text = (description + " " + job_title).lower()
        count = sum(1 for kw in ESG_KEYWORDS if kw in text)
        esg_relevant = count >= 2
        score = min(100.0, count * 15.0)
        return score, esg_relevant

    def _is_excluded_industry(self, description: str, job_title: str) -> bool:
        text = (description + " " + job_title).lower()
        return any(
            any(w in text for w in industry.split())
            for industry in _EXCLUDED_INDUSTRIES
        )

    def _zero_score(self, reason: str, flags: list) -> dict:
        return {
            "overall_score": 0.0,
            "breakdown": {k: 0.0 for k in _WEIGHTS},
            "matched_skills": [],
            "missing_skills": [],
            "flags": flags,
            "esg_relevant": False,
        }
