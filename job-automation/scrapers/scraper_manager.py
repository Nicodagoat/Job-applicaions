"""
Scraper manager — orchestrates all scrapers and saves results to the database.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import yaml
from pathlib import Path

from database.db import get_db
from backend.models.job import JobListingCreate
from backend.services.job_service import create_job, update_job_score
from ai.job_analyzer import JobAnalyzer
from ai.matching_engine import MatchingEngine
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.indeed_scraper import IndeedScraper

logger = logging.getLogger(__name__)

_PROFILE_PATH = Path(__file__).parent.parent / "config" / "profile.yaml"
with open(_PROFILE_PATH) as _f:
    _PROFILE = yaml.safe_load(_f)

# Build search terms from profile config
SEARCH_TERMS = (
    _PROFILE["job_titles"]["primary"][:4] +  # Top 4 primary titles
    _PROFILE["job_titles"]["secondary"][:2]  # Top 2 secondary
)

TARGET_LOCATIONS = _PROFILE["locations"]["target_countries"][:6]  # First 6 countries


class ScraperManager:
    def __init__(self):
        self.analyzer = JobAnalyzer()
        self.matcher = MatchingEngine()
        self.scrapers = [
            LinkedInScraper(),
            IndeedScraper(),
        ]

    def run(
        self,
        dry_run: bool = False,
        sources: Optional[list[str]] = None,
    ) -> dict:
        """
        Run all scrapers, analyse job descriptions, score matches,
        and save to the database.

        Returns a summary dict.
        """
        start_time = datetime.now()
        logger.info(f"[ScraperManager] Starting scrape run at {start_time}")

        all_raw_jobs: list[dict] = []

        # Collect raw jobs from all scrapers
        for scraper in self.scrapers:
            if sources and scraper.name not in sources:
                continue
            try:
                raw_jobs = scraper.scrape(
                    search_terms=SEARCH_TERMS,
                    locations=TARGET_LOCATIONS,
                )
                all_raw_jobs.extend(raw_jobs)
                logger.info(f"[ScraperManager] {scraper.name}: {len(raw_jobs)} raw jobs")
            except Exception as e:
                logger.error(f"[ScraperManager] Scraper {scraper.name} failed: {e}")

        # Filter excluded countries
        excluded = [c.lower() for c in _PROFILE["locations"]["excluded_countries"]]
        filtered = [
            j for j in all_raw_jobs
            if not any(
                excl in (j.get("country", "") + j.get("location", "")).lower()
                for excl in excluded
            )
        ]
        logger.info(
            f"[ScraperManager] {len(all_raw_jobs)} total → {len(filtered)} after geo filter"
        )

        new_count = 0
        high_match_count = 0
        saved_ids = []

        for raw in filtered:
            try:
                job_id, is_new = self._process_job(raw, dry_run)
                if job_id:
                    saved_ids.append(job_id)
                if is_new:
                    new_count += 1
            except Exception as e:
                logger.error(f"[ScraperManager] Error processing job: {e}")

        self._log_scraping_run(start_time, len(all_raw_jobs), new_count)

        summary = {
            "scraped_at": start_time.isoformat(),
            "total_found": len(all_raw_jobs),
            "after_geo_filter": len(filtered),
            "new_jobs_saved": new_count,
            "dry_run": dry_run,
        }
        logger.info(f"[ScraperManager] Run complete: {summary}")
        return summary

    def _process_job(self, raw: dict, dry_run: bool) -> tuple[Optional[int], bool]:
        """Analyse, score, and persist a single job. Returns (job_id, is_new)."""
        # Analyse description with AI
        description = raw.get("description", "")
        analysis = self.analyzer.analyze(description) if description else {}

        requirements = (
            analysis.get("required_skills", []) +
            analysis.get("preferred_skills", [])
        )

        # Score the match
        score_result = self.matcher.score(
            job_title=raw["job_title"],
            company=raw["company"],
            location=raw.get("location", ""),
            country=raw.get("country"),
            description=description,
            requirements=requirements,
            remote=raw.get("remote", False),
        )

        # Apply minimum score filter
        min_score = _PROFILE["application"]["min_match_score"]
        if score_result["overall_score"] < min_score:
            logger.debug(
                f"[ScraperManager] Skipping '{raw['job_title']}' "
                f"(score {score_result['overall_score']} < {min_score})"
            )
            return None, False

        if dry_run:
            logger.info(
                f"[DRY RUN] Would save: {raw['job_title']} @ {raw['company']} "
                f"(score={score_result['overall_score']})"
            )
            return None, False

        # Build model and save
        job_create = JobListingCreate(
            external_id=raw.get("external_id"),
            job_title=raw["job_title"],
            company=raw["company"],
            location=raw.get("location"),
            country=raw.get("country"),
            remote=raw.get("remote", False),
            source=raw["source"],
            source_url=raw.get("source_url"),
            description=description,
            requirements=requirements,
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            salary_currency=raw.get("salary_currency", "GBP"),
            posted_date=raw.get("posted_date"),
            esg_relevant=score_result["esg_relevant"],
            raw_data=raw.get("raw_data"),
        )

        saved = create_job(job_create)
        if not saved:
            return None, False  # Already existed (UNIQUE constraint)

        job_id = saved["id"]
        update_job_score(job_id, score_result["overall_score"], score_result["breakdown"])

        is_new = True
        return job_id, is_new

    def _log_scraping_run(
        self, start: datetime, total: int, new: int
    ) -> None:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO scraping_runs
                    (source, started_at, finished_at, status, jobs_found, jobs_new)
                VALUES (?, ?, datetime('now'), 'completed', ?, ?)
                """,
                ("all", start.isoformat(), total, new),
            )
            conn.commit()
