"""
LinkedIn Jobs scraper.

Uses the public LinkedIn Jobs search endpoint (no login required).
Respects rate limits strictly — LinkedIn aggressively blocks scrapers.

NOTE: LinkedIn's Terms of Service restrict automated access.
Use this only in compliance with your local laws and LinkedIn's policies.
For production use, consider the LinkedIn Job Search API (requires approval).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Optional
from urllib.parse import urlencode, quote_plus

import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# LinkedIn public job search — does NOT require login
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_JOB_URL = "https://www.linkedin.com/jobs/view/{job_id}"

# LinkedIn geo IDs for major target locations
LOCATION_IDS = {
    "United Kingdom": "101165590",
    "Germany": "101282230",
    "Netherlands": "102890719",
    "Belgium": "100565514",
    "France": "105015875",
    "Denmark": "104514075",
    "Sweden": "105117694",
    "Ireland": "104738515",
    "Luxembourg": "104042105",
}


class LinkedInScraper(BaseScraper):
    name = "linkedin"
    base_url = "linkedin.com"

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.settings["user_agent"],
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept": "application/json, text/html",
        })

    def scrape(
        self,
        search_terms: list[str],
        locations: list[str],
        max_per_search: int = 25,
    ) -> list[dict]:
        self._log_scrape_start(search_terms, locations)
        results = []

        for term in search_terms:
            for location in locations:
                geo_id = LOCATION_IDS.get(location)
                jobs = self._search_jobs(term, location, geo_id, max_per_search)
                results.extend(jobs)
                self._polite_delay()

        self.results = results
        logger.info(f"[linkedin] Scrape complete. Found {len(results)} jobs.")
        return results

    def _search_jobs(
        self,
        keyword: str,
        location: str,
        geo_id: Optional[str],
        max_results: int,
    ) -> list[dict]:
        params = {
            "keywords": keyword,
            "location": location,
            "start": 0,
            "count": min(max_results, 25),
            "f_TPR": "r604800",  # Past week
            "f_WT": "1,2,3",    # On-site, remote, hybrid
        }
        if geo_id:
            params["geoId"] = geo_id

        url = f"{LINKEDIN_SEARCH_URL}?{urlencode(params)}"

        try:
            self._polite_delay()
            response = self.session.get(
                url,
                timeout=self.settings["timeout_seconds"],
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[linkedin] Request failed for '{keyword}' in '{location}': {e}")
            return []

        return self._parse_job_listings(response.text, location)

    def _parse_job_listings(self, html: str, location: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.find_all("div", class_=re.compile(r"job-search-card")):
            try:
                job = self._parse_card(card, location)
                if job:
                    jobs.append(job)
                    self._log_job_found(job["job_title"], job["company"])
            except Exception as e:
                logger.debug(f"[linkedin] Error parsing card: {e}")

        return jobs

    def _parse_card(self, card, location: str) -> Optional[dict]:
        title_el = card.find("h3", class_=re.compile(r"base-search-card__title"))
        company_el = card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
        location_el = card.find("span", class_=re.compile(r"job-search-card__location"))
        link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
        date_el = card.find("time")

        if not title_el or not company_el:
            return None

        title = title_el.get_text(strip=True)
        company = company_el.get_text(strip=True)
        job_location = location_el.get_text(strip=True) if location_el else location
        url = link_el.get("href", "").split("?")[0] if link_el else ""
        posted_date = date_el.get("datetime") if date_el else None

        # Extract LinkedIn job ID
        job_id_match = re.search(r"/view/(\d+)", url)
        external_id = job_id_match.group(1) if job_id_match else hashlib.md5(
            f"{title}{company}".encode()
        ).hexdigest()[:12]

        remote = any(
            w in job_location.lower()
            for w in ["remote", "hybrid", "work from home"]
        )

        return {
            "external_id": external_id,
            "job_title": title,
            "company": company,
            "location": job_location,
            "country": location,
            "remote": remote,
            "source": "linkedin",
            "source_url": url,
            "description": "",  # Full description fetched separately
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "GBP",
            "posted_date": posted_date,
            "esg_relevant": False,
            "raw_data": {"card_text": card.get_text(" ", strip=True)},
        }

    def fetch_job_details(self, job_url: str) -> Optional[str]:
        """Fetch full job description from individual job page."""
        try:
            self._polite_delay()
            response = self.session.get(
                job_url,
                timeout=self.settings["timeout_seconds"],
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            desc_el = soup.find("div", class_=re.compile(r"show-more-less-html__markup"))
            if desc_el:
                return desc_el.get_text("\n", strip=True)
        except Exception as e:
            logger.debug(f"[linkedin] Failed to fetch job details from {job_url}: {e}")
        return None
