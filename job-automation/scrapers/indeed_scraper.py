"""
Indeed UK/EU jobs scraper.
Uses the public Indeed search pages.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

INDEED_SEARCH_URL = "https://uk.indeed.com/jobs"

INDEED_COUNTRY_DOMAINS = {
    "United Kingdom": "https://uk.indeed.com/jobs",
    "Germany": "https://de.indeed.com/jobs",
    "Netherlands": "https://nl.indeed.com/vacatures",
    "Belgium": "https://be.indeed.com/jobs",
    "France": "https://fr.indeed.com/emplois",
    "Ireland": "https://ie.indeed.com/jobs",
    "Denmark": "https://dk.indeed.com/jobs",
    "Sweden": "https://se.indeed.com/jobb",
}


class IndeedScraper(BaseScraper):
    name = "indeed"
    base_url = "indeed.com"

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.settings["user_agent"],
            "Accept-Language": "en-GB,en;q=0.9",
        })

    def scrape(
        self,
        search_terms: list[str],
        locations: list[str],
        max_per_search: int = 20,
    ) -> list[dict]:
        self._log_scrape_start(search_terms, locations)
        results = []

        for country in locations:
            base_url = INDEED_COUNTRY_DOMAINS.get(country, INDEED_SEARCH_URL)
            for term in search_terms:
                jobs = self._search_jobs(term, country, base_url, max_per_search)
                results.extend(jobs)
                self._polite_delay()

        self.results = results
        logger.info(f"[indeed] Scrape complete. Found {len(results)} jobs.")
        return results

    def _search_jobs(
        self, keyword: str, country: str, base_url: str, max_results: int
    ) -> list[dict]:
        params = {
            "q": keyword,
            "l": "",         # Empty = country-wide
            "fromage": "7",  # Past 7 days
            "limit": min(max_results, 20),
            "sort": "date",
        }
        url = f"{base_url}?{urlencode(params)}"

        try:
            self._polite_delay()
            response = self.session.get(
                url, timeout=self.settings["timeout_seconds"]
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[indeed] Request failed: {e}")
            return []

        return self._parse_results(response.text, country)

    def _parse_results(self, html: str, country: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for card in soup.find_all("div", class_=re.compile(r"job_seen_beacon|jobsearch-SerpJobCard")):
            try:
                job = self._parse_card(card, country)
                if job:
                    jobs.append(job)
                    self._log_job_found(job["job_title"], job["company"])
            except Exception as e:
                logger.debug(f"[indeed] Card parse error: {e}")

        return jobs

    def _parse_card(self, card, country: str) -> Optional[dict]:
        title_el = card.find("h2", class_=re.compile(r"jobTitle"))
        if not title_el:
            title_el = card.find("a", {"data-jk": True})

        company_el = card.find("span", class_=re.compile(r"companyName"))
        location_el = card.find("div", class_=re.compile(r"companyLocation"))
        salary_el = card.find("div", class_=re.compile(r"salary-snippet|estimated-salary"))
        link_el = card.find("a", href=re.compile(r"/rc/clk"))

        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        company = company_el.get_text(strip=True) if company_el else "Unknown"
        location = location_el.get_text(strip=True) if location_el else country
        salary_text = salary_el.get_text(strip=True) if salary_el else ""
        job_url = ""
        if link_el:
            href = link_el.get("href", "")
            job_url = f"https://uk.indeed.com{href}" if href.startswith("/") else href

        external_id = hashlib.md5(f"{title}{company}{country}".encode()).hexdigest()[:12]
        remote = any(w in location.lower() for w in ["remote", "home", "hybrid"])
        sal_min, sal_max, currency = self._extract_salary(salary_text)

        return {
            "external_id": external_id,
            "job_title": title,
            "company": company,
            "location": location,
            "country": country,
            "remote": remote,
            "source": "indeed",
            "source_url": job_url,
            "description": "",
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_currency": currency,
            "posted_date": None,
            "esg_relevant": False,
            "raw_data": {"salary_text": salary_text},
        }
