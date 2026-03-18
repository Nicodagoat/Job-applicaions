"""
Remotive API scraper — FREE, no API key needed.

Remotive lists remote jobs from companies worldwide.
Good source for sustainability/ESG remote roles based anywhere in Europe.
API: https://remotive.com/api/remote-jobs
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

import requests

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"

# Categories relevant to sustainability/ESG roles
RELEVANT_CATEGORIES = [
    "All Others",
    "Business",
    "Legal",
    "Management & Finance",
    "Project Management",
]

ESG_KEYWORDS = [
    "sustainability", "esg", "climate", "environmental", "carbon",
    "csrd", "net zero", "green", "renewable", "impact", "policy",
]


class RemotiveScraper(BaseScraper):
    """
    Free remote jobs API — no authentication required.
    Fetches remote roles that can be done from anywhere in Europe.
    """
    name = "remotive"
    base_url = "remotive.com"

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": self.settings["user_agent"],
        })

    def scrape(
        self,
        search_terms: list[str],
        locations: list[str],
        limit: int = 100,
    ) -> list[dict]:
        self._log_scrape_start(search_terms, locations)
        results: list[dict] = []
        seen_ids: set[str] = set()

        for term in ["sustainability", "ESG", "climate"] + search_terms[:2]:
            jobs = self._fetch_jobs(term, limit=50)
            for job in jobs:
                jid = str(job.get("id", ""))
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)
                parsed = self._parse_job(job)
                if parsed:
                    results.append(parsed)
                    self._log_job_found(parsed["job_title"], parsed["company"])
            self._polite_delay()

        logger.info(f"[remotive] Found {len(results)} remote jobs")
        return results

    def _fetch_jobs(self, search: str, limit: int = 50) -> list[dict]:
        try:
            resp = self.session.get(
                API_URL,
                params={"search": search, "limit": limit},
                timeout=self.settings["timeout_seconds"],
            )
            resp.raise_for_status()
            return resp.json().get("jobs", [])
        except Exception as e:
            logger.warning(f"[remotive] Request failed for '{search}': {e}")
            return []

    def _parse_job(self, job: dict) -> Optional[dict]:
        title   = job.get("title", "").strip()
        company = job.get("company_name", "").strip()
        if not title or not company:
            return None

        # Filter to ESG-relevant roles only
        text = (title + " " + job.get("description", "") + " " +
                " ".join(job.get("tags", []))).lower()
        if not any(kw in text for kw in ESG_KEYWORDS):
            return None

        job_id  = str(job.get("id", hashlib.md5(f"{title}{company}".encode()).hexdigest()[:12]))
        url     = job.get("url", "")
        desc    = job.get("description", "")
        tags    = job.get("tags", [])
        posted  = job.get("publication_date", "")

        return {
            "external_id":     f"remotive_{job_id}",
            "job_title":       title,
            "company":         company,
            "location":        "Remote (Europe)",
            "country":         "Remote",
            "remote":          True,
            "source":          "remotive",
            "source_url":      url,
            "description":     self._clean_html(desc),
            "salary_min":      None,
            "salary_max":      None,
            "salary_currency": "USD",
            "posted_date":     posted[:10] if posted else None,
            "esg_relevant":    True,
            "raw_data":        {"tags": tags, "category": job.get("category", "")},
        }

    @staticmethod
    def _clean_html(text: str) -> str:
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
