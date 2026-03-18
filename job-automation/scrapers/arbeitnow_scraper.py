"""
Arbeitnow API scraper — FREE, no API key needed.

Arbeitnow aggregates jobs from across Europe and the UK.
API docs: https://arbeitnow.com/api

This is the most reliable source for ESG/sustainability roles in Europe
because it requires no authentication and has excellent EU coverage.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional
from urllib.parse import urlencode

import requests

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

API_BASE = "https://arbeitnow.com/api/job-board-api"

# ESG-relevant search terms that work well with Arbeitnow
ESG_SEARCH_TERMS = [
    "sustainability",
    "ESG",
    "climate policy",
    "environmental",
    "CSRD",
    "net zero",
    "carbon",
]


class ArbeitnowScraper(BaseScraper):
    """
    Completely free, no-key scraper using the Arbeitnow public API.
    Returns real, live job listings from across Europe.
    """
    name = "arbeitnow"
    base_url = "arbeitnow.com"

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
        max_pages: int = 3,
    ) -> list[dict]:
        self._log_scrape_start(search_terms, locations)
        results: list[dict] = []
        seen_ids: set[str] = set()

        # Use our ESG terms plus the profile terms
        terms_to_search = list(dict.fromkeys(ESG_SEARCH_TERMS + search_terms[:3]))

        for term in terms_to_search:
            for page in range(1, max_pages + 1):
                jobs = self._fetch_page(term, page)
                if not jobs:
                    break  # No more pages

                new_jobs = 0
                for job in jobs:
                    jid = job.get("slug", "")
                    if jid and jid in seen_ids:
                        continue
                    if jid:
                        seen_ids.add(jid)
                    parsed = self._parse_job(job)
                    if parsed:
                        results.append(parsed)
                        new_jobs += 1
                        self._log_job_found(parsed["job_title"], parsed["company"])

                if new_jobs == 0:
                    break
                self._polite_delay()

        logger.info(f"[arbeitnow] Found {len(results)} jobs total")
        return results

    def _fetch_page(self, search: str, page: int) -> list[dict]:
        params = {"search": search, "page": page}
        url = f"{API_BASE}?{urlencode(params)}"
        try:
            resp = self.session.get(url, timeout=self.settings["timeout_seconds"])
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except requests.RequestException as e:
            logger.warning(f"[arbeitnow] Request failed for '{search}' page {page}: {e}")
            return []
        except Exception as e:
            logger.warning(f"[arbeitnow] Parse error: {e}")
            return []

    def _parse_job(self, job: dict) -> Optional[dict]:
        title   = job.get("title", "").strip()
        company = job.get("company_name", "").strip()
        if not title or not company:
            return None

        location = job.get("location", "")
        remote   = job.get("remote", False)
        url      = job.get("url", "")
        desc     = job.get("description", "")
        tags     = job.get("tags", [])
        slug     = job.get("slug", hashlib.md5(f"{title}{company}".encode()).hexdigest()[:12])
        created  = job.get("created_at", "")

        # Determine country from location string
        country = self._infer_country(location, job.get("tags", []))

        # Check if the job is in an excluded country (Italy)
        if "italy" in location.lower() or "italia" in location.lower():
            return None

        # Salary extraction
        sal_min, sal_max, currency = self._extract_salary(desc)

        esg_keywords = ["esg", "sustainability", "climate", "environmental", "carbon",
                        "csrd", "net zero", "ghg", "green", "taxonomy"]
        esg = any(kw in title.lower() or kw in " ".join(tags).lower() for kw in esg_keywords)

        return {
            "external_id":     slug,
            "job_title":       title,
            "company":         company,
            "location":        location,
            "country":         country,
            "remote":          remote,
            "source":          "arbeitnow",
            "source_url":      url,
            "description":     self._clean_html(desc),
            "salary_min":      sal_min,
            "salary_max":      sal_max,
            "salary_currency": currency,
            "posted_date":     created[:10] if created else None,
            "esg_relevant":    esg,
            "raw_data":        {"tags": tags, "job_types": job.get("job_types", [])},
        }

    def _infer_country(self, location: str, tags: list) -> str:
        """Best-effort country detection from location string."""
        loc = location.lower()
        tag_str = " ".join(tags).lower()
        country_hints = {
            "united kingdom": ["uk", "united kingdom", "london", "manchester", "edinburgh", "glasgow"],
            "Germany": ["germany", "deutschland", "berlin", "munich", "hamburg", "frankfurt"],
            "Netherlands": ["netherlands", "amsterdam", "rotterdam", "eindhoven"],
            "Belgium": ["belgium", "brussels", "bruxelles", "antwerp"],
            "France": ["france", "paris", "lyon", "marseille"],
            "Denmark": ["denmark", "copenhagen"],
            "Sweden": ["sweden", "stockholm", "gothenburg"],
            "Ireland": ["ireland", "dublin"],
            "Switzerland": ["switzerland", "zürich", "zurich", "geneva", "bern"],
            "Austria": ["austria", "vienna", "wien"],
            "Norway": ["norway", "oslo"],
            "Luxembourg": ["luxembourg"],
        }
        for country, hints in country_hints.items():
            if any(h in loc or h in tag_str for h in hints):
                return country
        if "remote" in loc or "worldwide" in loc:
            return "Remote"
        return location  # Return raw location if can't determine

    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip HTML tags from description."""
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
