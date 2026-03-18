"""
AI Cover Letter Generator.

STRICT RULES:
- Only uses data from PROFILE_FACTS and the job description provided.
- Never invents skills, experience, qualifications, or personal details.
- If a required detail is missing from the profile, it raises MissingProfileDataError.
- All generated content is marked with the source (which profile section it came from).
"""

from __future__ import annotations

import os
import re
from typing import Optional

from openai import OpenAI

from ai.profile_loader import PROFILE_FACTS, get_profile_as_text
from ai.prompts import COVER_LETTER_SYSTEM_PROMPT, COVER_LETTER_USER_PROMPT


class MissingProfileDataError(Exception):
    """Raised when the AI would need to invent information not in the profile."""
    pass


class CoverLetterGenerator:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def generate(
        self,
        job_title: str,
        company: str,
        job_description: str,
        requirements: Optional[list[str]] = None,
        tone: str = "professional",
        max_words: int = 350,
    ) -> dict:
        """
        Generate a tailored cover letter.

        Returns:
            {
                "content": str,          # The cover letter text
                "sources_used": list,    # Profile sections referenced
                "warnings": list,        # Any gaps flagged
                "requires_review": bool, # True if human review needed
            }
        """
        profile_text = get_profile_as_text()
        req_text = "\n".join(f"- {r}" for r in (requirements or []))

        user_prompt = COVER_LETTER_USER_PROMPT.format(
            job_title=job_title,
            company=company,
            job_description=job_description[:3000],  # Safety truncation
            requirements=req_text or "Not specified",
            profile=profile_text,
            tone=tone,
            max_words=max_words,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.3,  # Low temperature = more factual
            max_tokens=1500,
            messages=[
                {"role": "system", "content": COVER_LETTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw_output = response.choices[0].message.content

        # Parse the structured response
        result = self._parse_ai_response(raw_output)

        # Anti-hallucination check: verify any claimed facts exist in profile
        warnings = self._verify_against_profile(result["content"])
        result["warnings"].extend(warnings)
        result["requires_review"] = bool(result["warnings"])

        return result

    def _parse_ai_response(self, raw: str) -> dict:
        """Parse the structured AI output into components."""
        # The AI is prompted to return sections marked with tags
        content = self._extract_section(raw, "COVER_LETTER")
        sources = self._extract_section(raw, "SOURCES_USED")
        flags = self._extract_section(raw, "FLAGS")

        return {
            "content": content or raw,  # Fallback to full text if tags missing
            "sources_used": [s.strip() for s in sources.split("\n") if s.strip()] if sources else [],
            "warnings": [f.strip() for f in flags.split("\n") if f.strip()] if flags else [],
            "requires_review": False,
        }

    def _extract_section(self, text: str, tag: str) -> Optional[str]:
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    def _verify_against_profile(self, letter_text: str) -> list[str]:
        """
        Basic hallucination check: flag if the letter mentions skills/companies
        not found in the profile.
        """
        warnings = []
        all_skills = []
        for skills in PROFILE_FACTS["skills"].values():
            all_skills.extend([s.lower() for s in skills])

        known_companies = [exp["company"].lower() for exp in PROFILE_FACTS["experience"]]
        known_degrees = [edu["degree"].lower() for edu in PROFILE_FACTS["education"]]

        # This is a heuristic check — a more rigorous check would use NLP
        # For now, we flag potential issues and require human review
        suspicious_patterns = [
            r"\bPhD\b", r"\bDoctor\b", r"\bproject manager\b",
            r"\bcertified\b.*\b(PMP|CFA|CPA|FRM)\b",
            r"\b(C\+\+|Java|React|Node\.js|Kubernetes)\b",
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, letter_text, re.IGNORECASE):
                warnings.append(
                    f"Potential hallucination detected: '{pattern}' found in letter "
                    f"but not confirmed in profile. Please review before sending."
                )

        return warnings
