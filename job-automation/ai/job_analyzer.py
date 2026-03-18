"""
Job description analyser — uses free AI via llm_provider.py.
"""

from __future__ import annotations

import logging

from ai.llm_provider import chat_json
from ai.prompts import JOB_ANALYSIS_SYSTEM_PROMPT, JOB_ANALYSIS_USER_PROMPT

logger = logging.getLogger(__name__)


class JobAnalyzer:

    def analyze(self, job_description: str) -> dict:
        if not job_description or len(job_description.strip()) < 50:
            return self._empty()
        try:
            result = chat_json(
                system_prompt=JOB_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=JOB_ANALYSIS_USER_PROMPT.format(
                    job_description=job_description[:4000]
                ),
                temperature=0.1,
            )
            return self._validate(result)
        except Exception as e:
            logger.warning(f"[JobAnalyzer] AI unavailable, using empty analysis: {e}")
            return self._empty()

    def _validate(self, data: dict) -> dict:
        return {
            "required_skills":   data.get("required_skills", []),
            "preferred_skills":  data.get("preferred_skills", []),
            "seniority_level":   data.get("seniority_level", "unknown"),
            "remote":            data.get("remote", None),
            "salary_mentioned":  data.get("salary_mentioned", False),
            "visa_sponsorship":  data.get("visa_sponsorship", None),
            "esg_keywords":      data.get("esg_keywords", []),
            "summary":           data.get("summary", ""),
        }

    def _empty(self) -> dict:
        return {
            "required_skills": [], "preferred_skills": [],
            "seniority_level": "unknown", "remote": None,
            "salary_mentioned": False, "visa_sponsorship": None,
            "esg_keywords": [], "summary": "",
        }
