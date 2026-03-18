"""
Reed.co.uk API scraper — FREE API key (register at reed.co.uk/developers).

Reed is the UK's largest job board. Excellent for:
- UK sustainability and ESG roles
- Full job descriptions
- Salary information
- Real-time listings

Setup:
  1. Go to https://www.reed.co.uk/developers/jobseeker
  2. Register (free, takes 2 minutes)
  3. Copy your API key to config/.env:
     REED_API_KEY=your_key
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional
from urllib.parse import urlencode

import requests

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

REED_API_BASE = "https://www.reed.co.uk/api/1.0"


class ReedScraper(BaseScraper):
    """
    Reed.co.uk job search API — UK jobs with real descriptions.
    Requires a free API key from reed.co.uk/developers.
    """
    name = "reed"
    base_url = "reed.co.uk"

    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("REED_API_KEY", "")
        self.session = requests.Session()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _auth_header(self) -> dict:
        """Reed uses HTTP Basic auth with the API key as username."""
        token = base64.b64encode(f"{self.api_key}:".encode()).decode()
        return {"Authorization": f"Basic {token}", "Accept": "application/json"}

    def scrape(
        self,
        search_terms: list[str],
        locations: list[str],
        results_per_page: int = 25,
    ) -> list[dict]:
        if not self.is_configured():
            logger.info(
                "[reed] Skipping — no API key. "
                "Register free at https://www.reed.co.uk/developers/jobseeker"
            )
            return []

        self._log_scrape_start(search_terms, locations)
        results: list[dict] = []
        seen_ids: set[str] = set()

        uk_cities = ["London", "Manchester", "Edinburgh", "Bristol", "Birmingham"]

        for term in search_terms[:5]:
            for city in uk_cities[:3]:
                jobs = self._search(term, city, results_per_page)
                for job in jobs:
                    jid = str(job.get("jobId", ""))
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    parsed = self._parse_job(job)
                    if parsed:
                        results.append(parsed)
                        self._log_job_found(parsed["job_title"], parsed["company"])
                self._polite_delay()

        logger.info(f"[reed] Found {len(results)} UK jobs")
        return results

    def _search(self, keyword: str, location: str, results: int) -> list[dict]:
        params = {
            "keywords":         keyword,
            "locationName":     location,
            "resultsToTake":    results,
            "resultsToSkip":    0,
            "distanceFromLocation": 15,
        }
        url = f"{REED_API_BASE}/search?{urlencode(params)}"
        try:
            resp = self.session.get(
                url,
                headers=self._auth_header(),
                timeout=self.settings["timeout_seconds"],
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except requests.HTTPError as e:
            if resp.status_code == 401:
                logger.error("[reed] Invalid API key. Check REED_API_KEY in config/.env")
            else:
                logger.warning(f"[reed] HTTP error: {e}")
            return []
        except Exception as e:
            logger.warning(f"[reed] Request failed: {e}")
            return []

    def _parse_job(self, job: dict) -> Optional[dict]:
        title   = job.get("jobTitle", "").strip()
        company = job.get("employerName", "Unknown").strip()
        if not title or not company:
            return None

        job_id  = str(job.get("jobId", hashlib.md5(f"{title}{company}".encode()).hexdigest()[:12]))
        url     = job.get("jobUrl", f"https://www.reed.co.uk/jobs/{job_id}")
        location = job.get("locationName", "United Kingdom")
        salary_m = job.get("minimumSalary")
        salary_x = job.get("maximumSalary")
        desc     = job.get("jobDescription", "")
        posted   = job.get("date", "")
        remote   = "remote" in title.lower() or job.get("locationName", "").lower() == "remote"

        esg_kws = ["esg", "sustainability", "climate", "environmental", "carbon",
                   "csrd", "net zero", "green", "renewable", "ghg"]
        esg = any(kw in title.lower() or kw in desc.lower() for kw in esg_kws)

        return {
            "external_id":     f"reed_{job_id}",
            "job_title":       title,
            "company":         company,
            "location":        location,
            "country":         "United Kingdom",
            "remote":          remote,
            "source":          "reed",
            "source_url":      url,
            "description":     desc,
            "salary_min":      int(salary_m) if salary_m else None,
            "salary_max":      int(salary_x) if salary_x else None,
            "salary_currency": "GBP",
            "posted_date":     posted[:10] if posted else None,
            "esg_relevant":    esg,
            "raw_data":        {"jobId": job_id},
        }

    def fetch_full_description(self, job_id: str) -> Optional[str]:
        """Fetch the full job description from Reed."""
        try:
            resp = self.session.get(
                f"{REED_API_BASE}/jobs/{job_id}",
                headers=self._auth_header(),
                timeout=self.settings["timeout_seconds"],
            )
            resp.raise_for_status()
            return resp.json().get("jobDescription", "")
        except Exception:
            return None
