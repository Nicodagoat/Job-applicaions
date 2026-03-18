"""
Scraper manager — orchestrates all job sources and validates results.

Sources used (in order of reliability):
  1. Arbeitnow   — free, no key, EU+UK, best for ESG roles
  2. Remotive     — free, no key, remote roles worldwide
  3. Adzuna       — free API key, comprehensive UK+EU
  4. Reed         — free API key, UK specialist
  5. LinkedIn     — fallback (may be rate-limited)
  6. Indeed       — fallback (may be rate-limited)

After scraping, all jobs are validated to confirm they are still open.
Jobs in excluded countries (Italy) are filtered out automatically.
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
from scrapers.arbeitnow_scraper import ArbeitnowScraper
from scrapers.remotive_scraper import RemotiveScraper
from scrapers.adzuna_scraper import AdzunaScraper
from scrapers.reed_scraper import ReedScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.job_validator import JobValidator

logger = logging.getLogger(__name__)

_PROFILE_PATH = Path(__file__).parent.parent / "config" / "profile.yaml"
with open(_PROFILE_PATH) as _f:
    _PROFILE = yaml.safe_load(_f)

# Search terms from profile
SEARCH_TERMS = (
    _PROFILE["job_titles"]["primary"][:5] +
    _PROFILE["job_titles"]["secondary"][:3]
)

TARGET_LOCATIONS = _PROFILE["locations"]["target_countries"][:8]
EXCLUDED_COUNTRIES = [c.lower() for c in _PROFILE["locations"]["excluded_countries"]]


class ScraperManager:

    def __init__(self):
        self.analyzer  = JobAnalyzer()
        self.matcher   = MatchingEngine()
        self.validator = JobValidator()

        # Sources: reliable free ones first, key-based second, scraping last
        self.scrapers = [
            ArbeitnowScraper(),   # Free, no key, EU+UK
            RemotiveScraper(),    # Free, no key, remote
            AdzunaScraper(),      # Free API key (ADZUNA_APP_ID + ADZUNA_APP_KEY)
            ReedScraper(),        # Free API key (REED_API_KEY)
            LinkedInScraper(),    # Scraping fallback
            IndeedScraper(),      # Scraping fallback
        ]

    def run(
        self,
        dry_run: bool = False,
        sources: Optional[list[str]] = None,
        validate: bool = True,
    ) -> dict:
        """
        Full pipeline: scrape → filter → score → validate → save.
        """
        start_time = datetime.now()
        run_id = self._start_run_log()
        logger.info(f"[ScraperManager] Starting run at {start_time} (dry_run={dry_run})")

        all_raw: list[dict] = []

        # --- Step 1: Collect from all sources ---
        for scraper in self.scrapers:
            if sources and scraper.name not in sources:
                continue
            try:
                logger.info(f"[ScraperManager] Running {scraper.name}…")
                raw = scraper.scrape(
                    search_terms=SEARCH_TERMS,
                    locations=TARGET_LOCATIONS,
                )
                all_raw.extend(raw)
                logger.info(f"[ScraperManager] {scraper.name}: {len(raw)} jobs collected")
            except Exception as e:
                logger.error(f"[ScraperManager] {scraper.name} failed: {e}")

        # --- Step 2: Filter excluded countries ---
        filtered = [
            j for j in all_raw
            if not any(
                excl in (j.get("country", "") + " " + j.get("location", "")).lower()
                for excl in EXCLUDED_COUNTRIES
            )
        ]
        logger.info(f"[ScraperManager] {len(all_raw)} total → {len(filtered)} after geo-filter")

        # --- Step 3: Score and save ---
        new_ids:   list[int] = []
        new_count: int       = 0
        min_score = _PROFILE["application"]["min_match_score"]

        for raw in filtered:
            try:
                job_id, is_new = self._process_job(raw, dry_run, min_score)
                if job_id:
                    new_ids.append(job_id)
                if is_new:
                    new_count += 1
            except Exception as e:
                logger.error(f"[ScraperManager] Error processing '{raw.get('job_title')}': {e}")

        # --- Step 4: Validate that saved jobs are still open ---
        validation_results = {}
        if validate and new_ids and not dry_run:
            logger.info(f"[ScraperManager] Validating {len(new_ids)} new jobs…")
            validation_results = self.validator.validate_new_jobs(new_ids)
            logger.info(f"[ScraperManager] Validation: {validation_results}")

        # --- Step 5: Also re-validate stale existing jobs ---
        if not dry_run:
            self.validator.revalidate_stale_jobs(max_jobs=20)

        self._finish_run_log(run_id, len(all_raw), new_count)

        summary = {
            "scraped_at":       start_time.isoformat(),
            "sources_used":     [s.name for s in self.scrapers
                                 if not sources or s.name in sources],
            "total_found":      len(all_raw),
            "after_geo_filter": len(filtered),
            "new_jobs_saved":   new_count,
            "validation":       validation_results,
            "dry_run":          dry_run,
        }
        logger.info(f"[ScraperManager] Run complete: {summary}")
        return summary

    def _process_job(
        self, raw: dict, dry_run: bool, min_score: int
    ) -> tuple[Optional[int], bool]:
        """Score and save one job. Returns (job_id, is_new)."""
        description  = raw.get("description", "")

        # AI analysis (gracefully skipped if AI not configured)
        try:
            analysis = self.analyzer.analyze(description) if description else {}
        except Exception:
            analysis = {}

        requirements = (
            analysis.get("required_skills", []) +
            analysis.get("preferred_skills", [])
        )

        # Rule-based match scoring
        score_result = self.matcher.score(
            job_title=raw["job_title"],
            company=raw["company"],
            location=raw.get("location", ""),
            country=raw.get("country"),
            description=description,
            requirements=requirements,
            remote=raw.get("remote", False),
        )

        if score_result["overall_score"] < min_score:
            return None, False

        if dry_run:
            logger.info(
                f"[DRY RUN] {raw['job_title']} @ {raw['company']} | "
                f"score={score_result['overall_score']:.0f} | "
                f"source={raw['source']}"
            )
            return None, False

        # Save to database
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
            return None, False  # Duplicate (UNIQUE constraint)

        job_id = saved["id"]
        update_job_score(job_id, score_result["overall_score"], score_result["breakdown"])
        return job_id, True

    def _start_run_log(self) -> int:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO scraping_runs (source, status) VALUES ('all', 'running')"
            )
            conn.commit()
            return cur.lastrowid

    def _finish_run_log(self, run_id: int, total: int, new: int) -> None:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE scraping_runs
                SET finished_at=datetime('now'), status='completed',
                    jobs_found=?, jobs_new=?
                WHERE id=?
                """,
                (total, new, run_id),
            )
            conn.commit()
