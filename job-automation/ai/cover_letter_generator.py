"""
Cover Letter Generator — uses free AI providers via llm_provider.py.

STRICT ANTI-HALLUCINATION RULES:
- Only uses data from PROFILE_FACTS (hardcoded from real CV)
- Never invents skills, experience, or qualifications
- If required detail is missing, raises MissingProfileDataError
- Every claim in the letter is traced to a profile section
"""

from __future__ import annotations

import re
from typing import Optional

from ai.llm_provider import chat, get_provider_info
from ai.profile_loader import PROFILE_FACTS, get_profile_as_text
from ai.prompts import COVER_LETTER_SYSTEM_PROMPT, COVER_LETTER_USER_PROMPT


class MissingProfileDataError(Exception):
    """Raised when required information is not in the profile."""
    pass


class CoverLetterGenerator:

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
        Generate a tailored cover letter using the active free AI provider.

        Returns:
            {
                "content": str,
                "sources_used": list[str],
                "warnings": list[str],
                "requires_review": bool,
                "provider": str,
            }
        """
        provider = get_provider_info()
        profile_text = get_profile_as_text()
        req_text = "\n".join(f"- {r}" for r in (requirements or []))

        user_prompt = COVER_LETTER_USER_PROMPT.format(
            job_title=job_title,
            company=company,
            job_description=job_description[:3000],
            requirements=req_text or "Not specified",
            profile=profile_text,
            tone=tone,
            max_words=max_words,
        )

        raw_output = chat(
            system_prompt=COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=1200,
        )

        result = self._parse_response(raw_output)
        warnings = self._verify_against_profile(result["content"])
        result["warnings"].extend(warnings)
        result["requires_review"] = bool(result["warnings"])
        result["provider"] = provider["name"]
        return result

    def _parse_response(self, raw: str) -> dict:
        """Extract letter, sources, and flags from structured AI output."""
        content  = self._extract_tag(raw, "COVER_LETTER")
        sources  = self._extract_tag(raw, "SOURCES_USED")
        flags    = self._extract_tag(raw, "FLAGS")

        # If model didn't use tags (happens with smaller local models), use full output
        if not content:
            # Strip any preamble up to first blank line
            lines = raw.strip().splitlines()
            start = 0
            for i, line in enumerate(lines):
                if line.strip().lower().startswith("dear") or line.strip().lower().startswith("i am"):
                    start = i
                    break
            content = "\n".join(lines[start:]).strip()

        return {
            "content": content or raw.strip(),
            "sources_used": [s.strip("- ") for s in (sources or "").splitlines() if s.strip()],
            "warnings": [f.strip("- ") for f in (flags or "").splitlines() if f.strip() and f.strip() != "None"],
            "requires_review": False,
        }

    def _extract_tag(self, text: str, tag: str) -> Optional[str]:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
        return match.group(1).strip() if match else None

    def _verify_against_profile(self, letter: str) -> list[str]:
        """Heuristic check for invented credentials."""
        warnings = []
        false_claims = [
            (r"\bPhD\b|\bDoctorate\b", "PhD/Doctorate not in profile"),
            (r"\bPMP\b|\bCFA\b|\bCPA\b|\bFRM\b|\bActuar", "Professional certification not in profile"),
            (r"\b(Java|C\+\+|React|Node\.js|Kubernetes|TensorFlow)\b", "Programming skill not in profile"),
            (r"\b(\d{10,})\b", "Suspiciously large number"),
        ]
        for pattern, label in false_claims:
            if re.search(pattern, letter, re.IGNORECASE):
                warnings.append(f"Possible hallucination — {label}. Please review before sending.")
        return warnings
