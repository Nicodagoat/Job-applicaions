"""
Base scraper class.
All scrapers inherit from this and implement `scrape()`.
"""

from __future__ import annotations

import logging
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import yaml
from pathlib import Path


_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
with open(_SETTINGS_PATH) as _f:
    _SETTINGS = yaml.safe_load(_f)

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base scraper with rate limiting and logging.
    """

    name: str = "base"
    base_url: str = ""

    def __init__(self):
        self.settings = _SETTINGS["scraping"]
        self.rate_limit = self.settings["rate_limit_per_site"].get(
            self.base_url.replace("https://", "").replace("www.", ""),
            self.settings["rate_limit_per_site"]["default"],
        )
        self._request_count = 0
        self._window_start = time.time()
        self.results: list[dict] = []

    @abstractmethod
    def scrape(self, search_terms: list[str], locations: list[str]) -> list[dict]:
        """
        Perform the scrape. Must return a list of job dicts matching the schema:
        {
            "external_id": str,
            "job_title": str,
            "company": str,
            "location": str,
            "country": str,
            "remote": bool,
            "source": str,
            "source_url": str,
            "description": str,
            "salary_min": int | None,
            "salary_max": int | None,
            "salary_currency": str,
            "posted_date": str | None,
            "esg_relevant": bool,
            "raw_data": dict,
        }
        """
        ...

    def _polite_delay(self) -> None:
        """Enforce rate limiting with jitter to avoid detection."""
        now = time.time()
        elapsed = now - self._window_start

        if elapsed >= 60:
            self._request_count = 0
            self._window_start = now
        elif self._request_count >= self.rate_limit:
            sleep_time = 60 - elapsed + random.uniform(1, 5)
            logger.info(f"[{self.name}] Rate limit reached. Sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
            self._request_count = 0
            self._window_start = time.time()

        base_delay = self.settings["request_delay_seconds"]
        jitter = random.uniform(0.5, 2.0)
        time.sleep(base_delay + jitter)
        self._request_count += 1

    def _log_scrape_start(self, search_terms: list[str], locations: list[str]) -> None:
        logger.info(
            f"[{self.name}] Starting scrape | terms={search_terms} | locations={locations}"
        )

    def _log_job_found(self, title: str, company: str) -> None:
        logger.debug(f"[{self.name}] Found: {title} @ {company}")

    @staticmethod
    def _extract_salary(text: str) -> tuple[Optional[int], Optional[int], str]:
        """
        Attempt to extract salary range from text.
        Returns (min, max, currency).
        """
        import re
        # Pattern: £35,000 - £45,000 or €40k-€50k
        patterns = [
            r"£\s*(\d[\d,]*)\s*(?:k)?\s*[-–to]+\s*£\s*(\d[\d,]*)\s*(?:k)?",
            r"€\s*(\d[\d,]*)\s*(?:k)?\s*[-–to]+\s*€\s*(\d[\d,]*)\s*(?:k)?",
            r"(\d[\d,]*)\s*(?:k)?\s*[-–to]+\s*(\d[\d,]*)\s*(?:k)?\s*(GBP|EUR|USD)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                low = int(match.group(1).replace(",", ""))
                high = int(match.group(2).replace(",", ""))
                # Handle 'k' suffix
                if "k" in text[match.start():match.end()].lower():
                    low *= 1000
                    high *= 1000
                currency = "GBP" if "£" in pattern else "EUR"
                return low, high, currency
        return None, None, "GBP"
