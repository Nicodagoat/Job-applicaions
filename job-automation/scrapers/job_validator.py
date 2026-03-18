"""
Job Validator — verifies job listings are still open before applying.

This is a critical safety feature:
- Never wastes time applying to a closed role
- Checks if the job URL still returns a real job page
- Detects common "job closed" and "job expired" patterns
- Marks closed jobs in the database so they're hidden from the dashboard
- Re-validates jobs that haven't been checked recently
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

import requests

from database.db import get_db, rows_to_list

logger = logging.getLogger(__name__)

# Phrases that indicate a job is no longer available
CLOSED_PATTERNS = [
    r"this job is no longer available",
    r"this job has expired",
    r"this listing has closed",
    r"vacancy has been filled",
    r"position has been filled",
    r"this role has been filled",
    r"no longer accepting applications",
    r"application deadline has passed",
    r"job not found",
    r"sorry, this job",
    r"position is no longer",
    r"role is no longer",
    r"404",
    r"page not found",
]

# How many hours before we re-check a job we've already validated
REVALIDATION_HOURS = 24

# Timeout for validation requests (keep short — we don't need full page load)
VALIDATION_TIMEOUT = 10


class JobValidator:
    """
    Checks whether job listings are still open and updates the database.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def validate_new_jobs(self, job_ids: list[int]) -> dict:
        """
        Validate a list of newly discovered job IDs.
        Returns counts of active vs closed.
        """
        active = 0
        closed = 0
        for job_id in job_ids:
            result = self._validate_one(job_id)
            if result:
                active += 1
            else:
                closed += 1
            time.sleep(1)  # Gentle pace
        return {"active": active, "closed": closed, "total": len(job_ids)}

    def revalidate_stale_jobs(self, max_jobs: int = 50) -> dict:
        """
        Re-check jobs that haven't been validated in REVALIDATION_HOURS.
        Call this periodically to keep the database fresh.
        """
        cutoff = (datetime.now() - timedelta(hours=REVALIDATION_HOURS)).isoformat()
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, source_url, source FROM job_listings
                WHERE is_active = 1
                  AND (verified_at IS NULL OR verified_at < ?)
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (cutoff, max_jobs),
            ).fetchall()
        jobs = rows_to_list(rows)
        logger.info(f"[Validator] Re-validating {len(jobs)} stale jobs")

        active = closed = 0
        for job in jobs:
            result = self._validate_one(job["id"], job.get("source_url"), job.get("source"))
            if result:
                active += 1
            else:
                closed += 1
            time.sleep(1.5)

        return {"revalidated": len(jobs), "active": active, "closed": closed}

    def _validate_one(
        self,
        job_id: int,
        url: Optional[str] = None,
        source: Optional[str] = None,
    ) -> bool:
        """
        Validate a single job. Returns True if active, False if closed.
        Updates the database accordingly.
        """
        # Fetch URL from DB if not provided
        if not url:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT source_url, source FROM job_listings WHERE id = ?", (job_id,)
                ).fetchone()
                if row:
                    url = row["source_url"]
                    source = row["source"]

        if not url:
            # No URL to check — assume active, mark as verified
            self._mark_verified(job_id, is_active=True, reason=None)
            return True

        # Source-specific validators
        if source == "arbeitnow":
            is_open = self._validate_arbeitnow(url)
        elif source == "reed":
            is_open = self._validate_reed(url)
        else:
            is_open = self._validate_generic(url)

        reason = None if is_open else "URL check failed or job closed message detected"
        self._mark_verified(job_id, is_active=is_open, reason=reason)

        if not is_open:
            logger.info(f"[Validator] Job {job_id} marked as CLOSED: {url[:80]}")

        return is_open

    def _validate_generic(self, url: str) -> bool:
        """
        Generic URL validation:
        1. Check HTTP status code
        2. Scan page content for "job closed" phrases
        """
        try:
            # Try HEAD request first (faster, less data)
            resp = self.session.head(
                url, timeout=VALIDATION_TIMEOUT, allow_redirects=True
            )
            if resp.status_code == 404:
                return False
            if resp.status_code >= 400:
                return False

            # If we got redirected to a generic listing page, likely closed
            final_url = resp.url
            if self._looks_like_listing_redirect(url, final_url):
                return False

            # For APIs that return 200 even for closed jobs,
            # do a GET and check content
            if "arbeitnow" in url or "reed.co.uk" in url or "linkedin.com" in url:
                return self._check_page_content(url)

            return True

        except requests.exceptions.SSLError:
            # SSL issues — assume open (common on some job boards)
            return True
        except requests.exceptions.ConnectionError:
            # Site unreachable — don't mark as closed (might be temporary)
            return True
        except requests.exceptions.Timeout:
            return True
        except Exception as e:
            logger.debug(f"[Validator] Error checking {url}: {e}")
            return True  # Benefit of the doubt

    def _validate_arbeitnow(self, url: str) -> bool:
        """Arbeitnow jobs have direct URLs — a 404 means the job is gone."""
        try:
            resp = self.session.get(url, timeout=VALIDATION_TIMEOUT, allow_redirects=True)
            if resp.status_code == 404:
                return False
            # Check for "job not found" in content
            return not self._has_closed_phrase(resp.text)
        except Exception:
            return True

    def _validate_reed(self, url: str) -> bool:
        """Reed returns 200 even for expired jobs — check the content."""
        return self._check_page_content(url)

    def _check_page_content(self, url: str) -> bool:
        """
        Fetch page and scan for phrases indicating the job is closed.
        """
        try:
            resp = self.session.get(
                url, timeout=VALIDATION_TIMEOUT, allow_redirects=True
            )
            if resp.status_code == 404:
                return False
            return not self._has_closed_phrase(resp.text)
        except Exception:
            return True

    def _has_closed_phrase(self, html: str) -> bool:
        """Returns True if the page contains a 'job closed' phrase."""
        text = html.lower()
        return any(re.search(p, text) for p in CLOSED_PATTERNS)

    def _looks_like_listing_redirect(self, original: str, final: str) -> bool:
        """
        Detect if a redirect has sent us from a specific job page
        to a generic job search listing (sign that the job is gone).
        """
        orig_path  = urlparse(original).path
        final_path = urlparse(final).path
        # If we started with a long path and ended up at / or /jobs, it's likely a redirect
        if len(orig_path) > 10 and len(final_path) <= 6:
            return True
        return False

    def _mark_verified(
        self, job_id: int, is_active: bool, reason: Optional[str]
    ) -> None:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE job_listings
                SET is_active = ?, verified_at = datetime('now'),
                    closed_reason = ?, last_updated = datetime('now')
                WHERE id = ?
                """,
                (1 if is_active else 0, reason, job_id),
            )
            conn.commit()

    def get_validation_stats(self) -> dict:
        with get_db() as conn:
            total  = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM job_listings WHERE is_active=1").fetchone()[0]
            closed = conn.execute("SELECT COUNT(*) FROM job_listings WHERE is_active=0").fetchone()[0]
            unverified = conn.execute(
                "SELECT COUNT(*) FROM job_listings WHERE verified_at IS NULL"
            ).fetchone()[0]
        return {
            "total": total,
            "active": active,
            "closed": closed,
            "unverified": unverified,
            "active_pct": round(active / total * 100) if total else 0,
        }
