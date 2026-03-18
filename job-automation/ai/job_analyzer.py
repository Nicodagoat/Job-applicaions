"""
Job description analyser.
Extracts structured requirements from raw job postings using AI.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from openai import OpenAI

from ai.prompts import JOB_ANALYSIS_SYSTEM_PROMPT, JOB_ANALYSIS_USER_PROMPT


class JobAnalyzer:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def analyze(self, job_description: str) -> dict:
        """
        Analyze a job description and return structured data.

        Returns a dict with:
        - required_skills, preferred_skills, seniority_level,
          remote, salary_mentioned, visa_sponsorship,
          esg_keywords, summary
        """
        if not job_description or len(job_description.strip()) < 50:
            return self._empty_analysis()

        prompt = JOB_ANALYSIS_USER_PROMPT.format(
            job_description=job_description[:4000]
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": JOB_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            result = json.loads(response.choices[0].message.content)
            return self._validate_analysis(result)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[JobAnalyzer] Error: {e}")
            return self._empty_analysis()

    def _validate_analysis(self, data: dict) -> dict:
        """Ensure all expected keys are present with safe defaults."""
        return {
            "required_skills": data.get("required_skills", []),
            "preferred_skills": data.get("preferred_skills", []),
            "seniority_level": data.get("seniority_level", "unknown"),
            "remote": data.get("remote", None),
            "salary_mentioned": data.get("salary_mentioned", False),
            "visa_sponsorship": data.get("visa_sponsorship", None),
            "esg_keywords": data.get("esg_keywords", []),
            "summary": data.get("summary", ""),
        }

    def _empty_analysis(self) -> dict:
        return {
            "required_skills": [],
            "preferred_skills": [],
            "seniority_level": "unknown",
            "remote": None,
            "salary_mentioned": False,
            "visa_sponsorship": None,
            "esg_keywords": [],
            "summary": "",
        }
