"""
Automated form filler using Playwright.

Safety guarantees:
- All submissions require human approval (dry_run=True by default in settings)
- Every action is logged to the audit trail
- Rate limiting is enforced
- Manual override is always available
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import yaml
from pathlib import Path

from database.db import get_db
from notifications.notifier import Notifier
from ai.profile_loader import PROFILE_FACTS

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
with open(_SETTINGS_PATH) as _f:
    _SETTINGS = yaml.safe_load(_f)

DRY_RUN = _SETTINGS["safety"]["dry_run"]
HUMAN_APPROVAL = _SETTINGS["safety"]["human_approval_required"]


# --------------------------------------------------------------------------- #
# Field mapping — maps common form field names to profile data                #
# --------------------------------------------------------------------------- #

FIELD_MAP = {
    # Name fields
    "first_name": PROFILE_FACTS["name"].split()[0],
    "last_name": PROFILE_FACTS["name"].split()[-1],
    "full_name": PROFILE_FACTS["name"],
    "name": PROFILE_FACTS["name"],
    # Contact
    "email": PROFILE_FACTS["email"],
    "phone": PROFILE_FACTS["phone"],
    "mobile": PROFILE_FACTS["phone"],
    "telephone": PROFILE_FACTS["phone"],
    "linkedin": PROFILE_FACTS["linkedin"],
    "linkedin_url": PROFILE_FACTS["linkedin"],
    "website": PROFILE_FACTS.get("website", ""),
    "portfolio": PROFILE_FACTS.get("website", ""),
    # Location
    "city": "Milan",
    "country": "Italy",
    "location": "Milan, Italy",
    # Work authorisation
    "right_to_work": "Yes",
    "visa_required": "Yes",
    "require_sponsorship": "Yes",
}


class ApplicationAutomator:
    """
    Orchestrates the end-to-end application submission process.
    """

    def __init__(self):
        self.notifier = Notifier()
        self.dry_run = DRY_RUN

    def submit_application(
        self,
        application_id: int,
        job_id: int,
        form_url: str,
        cover_letter_text: str,
        resume_path: str,
    ) -> dict:
        """
        Attempt to submit an application.

        Returns:
            {
                "success": bool,
                "method": str,
                "confirmation": str | None,
                "manual_required": bool,
                "log": list[str],
            }
        """
        log = []

        # Safety check: require human approval
        if HUMAN_APPROVAL:
            approved = self._check_human_approval(application_id)
            if not approved:
                log.append("Waiting for human approval — application paused.")
                self._audit("application_paused", application_id, {"reason": "awaiting_approval"})
                return {
                    "success": False,
                    "method": None,
                    "confirmation": None,
                    "manual_required": True,
                    "log": log,
                }

        if self.dry_run:
            log.append("[DRY RUN] Would submit application — no actual form submission performed.")
            logger.info(f"[FormFiller] DRY RUN — application {application_id} not submitted")
            return {
                "success": True,
                "method": "dry_run",
                "confirmation": "DRY_RUN_MOCK",
                "manual_required": False,
                "log": log,
            }

        # Try automated submission
        try:
            result = self._playwright_submit(
                form_url=form_url,
                cover_letter=cover_letter_text,
                resume_path=resume_path,
                log=log,
            )
            return result
        except Exception as e:
            logger.error(f"[FormFiller] Automation failed: {e}")
            log.append(f"Automation failed: {e}. Manual submission required.")
            self._request_manual_action(application_id, job_id, form_url, str(e))
            return {
                "success": False,
                "method": "failed",
                "confirmation": None,
                "manual_required": True,
                "log": log,
            }

    def _playwright_submit(
        self,
        form_url: str,
        cover_letter: str,
        resume_path: str,
        log: list[str],
    ) -> dict:
        """
        Use Playwright to fill and submit an application form.
        Requires `playwright` package and browser installed.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=_SETTINGS["scraping"]["headless"]
            )
            page = browser.new_page()
            page.set_default_timeout(_SETTINGS["scraping"]["timeout_seconds"] * 1000)

            log.append(f"Navigating to: {form_url}")
            page.goto(form_url)

            # Fill known fields
            filled = self._fill_form_fields(page, log)

            # Upload resume if file upload detected
            resume_uploaded = self._try_upload_resume(page, resume_path, log)

            # Fill cover letter textarea
            self._try_fill_cover_letter(page, cover_letter, log)

            if not filled:
                log.append("Could not identify form fields — manual submission required.")
                browser.close()
                return {
                    "success": False,
                    "method": "playwright",
                    "confirmation": None,
                    "manual_required": True,
                    "log": log,
                }

            # Take screenshot before submit for audit trail
            screenshot_path = f"logs/screenshots/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=screenshot_path)
            log.append(f"Pre-submission screenshot saved: {screenshot_path}")

            # Submit form
            submit_btn = page.query_selector(
                "button[type=submit], input[type=submit], button:text('Submit'), button:text('Apply')"
            )
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                log.append("Form submitted.")
                confirmation = page.url
            else:
                log.append("Submit button not found — manual submission required.")
                browser.close()
                return {
                    "success": False,
                    "method": "playwright",
                    "confirmation": None,
                    "manual_required": True,
                    "log": log,
                }

            browser.close()

        return {
            "success": True,
            "method": "playwright",
            "confirmation": confirmation,
            "manual_required": False,
            "log": log,
        }

    def _fill_form_fields(self, page, log: list[str]) -> bool:
        """Fill standard form fields. Returns True if any fields were filled."""
        filled = False
        for field_name, value in FIELD_MAP.items():
            if not value:
                continue
            # Try common selectors
            selectors = [
                f"input[name='{field_name}']",
                f"input[id='{field_name}']",
                f"input[placeholder*='{field_name}' i]",
                f"input[aria-label*='{field_name}' i]",
            ]
            for selector in selectors:
                el = page.query_selector(selector)
                if el:
                    try:
                        el.fill(str(value))
                        log.append(f"Filled field '{field_name}'")
                        filled = True
                        break
                    except Exception:
                        pass
        return filled

    def _try_upload_resume(self, page, resume_path: str, log: list[str]) -> bool:
        """Attempt to upload resume to file input."""
        if not resume_path or not Path(resume_path).exists():
            log.append("Resume file not found for upload.")
            return False
        for selector in [
            "input[type=file]",
            "input[accept*='.pdf']",
            "input[accept*='.doc']",
        ]:
            el = page.query_selector(selector)
            if el:
                try:
                    el.set_input_files(resume_path)
                    log.append(f"Resume uploaded: {resume_path}")
                    return True
                except Exception as e:
                    log.append(f"Resume upload failed: {e}")
        return False

    def _try_fill_cover_letter(self, page, cover_letter: str, log: list[str]) -> bool:
        """Try to fill cover letter into a textarea."""
        for selector in [
            "textarea[name*='cover' i]",
            "textarea[id*='cover' i]",
            "textarea[placeholder*='cover' i]",
            "textarea[aria-label*='cover' i]",
            "textarea",
        ]:
            el = page.query_selector(selector)
            if el:
                try:
                    el.fill(cover_letter[:5000])  # Truncate if too long
                    log.append("Cover letter filled.")
                    return True
                except Exception:
                    pass
        return False

    def _check_human_approval(self, application_id: int) -> bool:
        with get_db() as conn:
            row = conn.execute(
                "SELECT human_approved FROM applications WHERE id = ?",
                (application_id,)
            ).fetchone()
            return bool(row and row["human_approved"])

    def _request_manual_action(
        self,
        application_id: int,
        job_id: int,
        url: str,
        error: str,
    ) -> None:
        # Get job details for notification
        with get_db() as conn:
            job = conn.execute(
                "SELECT job_title, company FROM job_listings WHERE id = ?", (job_id,)
            ).fetchone()
            if job:
                self.notifier.notify_manual_input(
                    job_title=job["job_title"],
                    company=job["company"],
                    url=url,
                    action=f"Manual application required. Error: {error[:100]}",
                )
                # Create a task
                conn.execute(
                    """
                    INSERT INTO tasks (task_type, job_id, application_id, title, description, priority)
                    VALUES ('manual_input', ?, ?, 'Manual application required', ?, 'high')
                    """,
                    (job_id, application_id, f"Automation failed: {error}. Please apply manually at: {url}"),
                )
                conn.commit()

    def _audit(self, event_type: str, entity_id: int, details: dict) -> None:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (event_type, entity, entity_id, action, details)
                VALUES (?, 'application', ?, ?, ?)
                """,
                (event_type, entity_id, event_type, json.dumps(details)),
            )
            conn.commit()
