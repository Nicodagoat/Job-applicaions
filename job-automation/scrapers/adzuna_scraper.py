"""
Adzuna API scraper — FREE API key (register once at developer.adzuna.com).

Adzuna is one of the best job search APIs:
- Covers UK, Germany, Netherlands, France, Belgium, Austria, and more
- Returns full job descriptions
- Free tier: 250 requests/month (more than enough for daily use)
- Very comprehensive for sustainability/ESG roles

Setup:
  1. Go to https://developer.adzuna.com/
  2. Click "Register" (takes 2 minutes, completely free)
  3. Copy your App ID and App Key to config/.env:
     ADZUNA_APP_ID=your_id
     ADZUNA_APP_KEY=your_key
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional
from urllib.parse import urlencode

import requests

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Adzuna country codes mapped to our target countries
ADZUNA_COUNTRIES = {
    "United Kingdom": "gb",
    "Germany":        "de",
    "Netherlands":    "nl",
    "France":         "fr",
    "Belgium":        "be",
    "Austria":        "at",
    "Switzerland":    "ch",
    "Ireland":        "ie",
}

API_BASE = "https://api.adzuna.com/v1/api/jobs"


class AdzunaScraper(BaseScraper):
    """
    Adzuna job search API — requires a free API key.
    Best source for comprehensive UK and EU job coverage.
    """
    name = "adzuna"
    base_url = "api.adzuna.com"

    def __init__(self):
        super().__init__()
        self.app_id  = os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = os.environ.get("ADZUNA_APP_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_key)

    def scrape(
        self,
        search_terms: list[str],
        locations: list[str],
        max_pages: int = 2,
        results_per_page: int = 20,
    ) -> list[dict]:
        if not self.is_configured():
            logger.info(
                "[adzuna] Skipping — no API key configured. "
                "Register free at https://developer.adzuna.com/"
            )
            return []

        self._log_scrape_start(search_terms, locations)
        results: list[dict] = []
        seen_ids: set[str] = set()

        # Use the top search terms
        for term in search_terms[:4]:
            for country_name in locations:
                country_code = ADZUNA_COUNTRIES.get(country_name)
                if not country_code:
                    continue
                for page in range(1, max_pages + 1):
                    jobs = self._fetch_page(term, country_code, page, results_per_page)
                    if not jobs:
                        break
                    for job in jobs:
                        jid = str(job.get("id", ""))
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)
                        parsed = self._parse_job(job, country_name)
                        if parsed:
                            results.append(parsed)
                            self._log_job_found(parsed["job_title"], parsed["company"])
                    self._polite_delay()

        logger.info(f"[adzuna] Found {len(results)} jobs")
        return results

    def _fetch_page(
        self, keyword: str, country: str, page: int, per_page: int
    ) -> list[dict]:
        params = {
            "app_id":              self.app_id,
            "app_key":             self.app_key,
            "results_per_page":    per_page,
            "what":                keyword,
            "sort_by":             "date",
            "content-type":        "application/json",
        }
        url = f"{API_BASE}/{country}/search/{page}?{urlencode(params)}"
        try:
            resp = self.session.get(url, timeout=self.settings["timeout_seconds"])
            resp.raise_for_status()
            return resp.json().get("results", [])
        except requests.HTTPError as e:
            if resp.status_code == 401:
                logger.error("[adzuna] Invalid API credentials. Check ADZUNA_APP_ID and ADZUNA_APP_KEY in config/.env")
            else:
                logger.warning(f"[adzuna] HTTP {resp.status_code} for '{keyword}' in {country}")
            return []
        except Exception as e:
            logger.warning(f"[adzuna] Request failed: {e}")
            return []

    def _parse_job(self, job: dict, country: str) -> Optional[dict]:
        title   = job.get("title", "").strip()
        company = (job.get("company", {}) or {}).get("display_name", "Unknown").strip()
        if not title or not company:
            return None

        location_data = job.get("location", {}) or {}
        location = location_data.get("display_name", "")

        # Skip Italian roles
        if "italy" in location.lower() or "italia" in location.lower():
            return None

        url      = job.get("redirect_url", "")
        desc     = job.get("description", "")
        salary_m = job.get("salary_min")
        salary_x = job.get("salary_max")
        created  = job.get("created", "")
        job_id   = str(job.get("id", hashlib.md5(f"{title}{company}".encode()).hexdigest()[:12]))

        currency = "GBP" if country == "United Kingdom" else "EUR"
        remote   = "remote" in title.lower() or "remote" in (location or "").lower()

        esg_kws = ["esg", "sustainability", "climate", "environmental", "carbon",
                   "csrd", "net zero", "green", "taxonomy", "ghg", "policy"]
        esg = any(kw in title.lower() or kw in desc.lower() for kw in esg_kws)

        return {
            "external_id":     f"adzuna_{job_id}",
            "job_title":       title,
            "company":         company,
            "location":        location,
            "country":         country,
            "remote":          remote,
            "source":          "adzuna",
            "source_url":      url,
            "description":     desc,
            "salary_min":      int(salary_m) if salary_m else None,
            "salary_max":      int(salary_x) if salary_x else None,
            "salary_currency": currency,
            "posted_date":     created[:10] if created else None,
            "esg_relevant":    esg,
            "raw_data":        {"adref": job.get("adref"), "category": job.get("category", {})},
        }
