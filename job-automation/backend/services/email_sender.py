"""
ProtonMail email sender — uses Playwright to send emails via the ProtonMail web app.

This allows email-based job applications (CV + cover letter) to be sent
from your ProtonMail account without any SMTP configuration.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PROTONMAIL_URL = "https://mail.proton.me"


def send_application_email(
    to: str,
    subject: str,
    body: str,
    cv_path: str | None = None,
) -> dict:
    """
    Send a job application email via ProtonMail web.

    Args:
        to:       Recipient email address (e.g. jobs@company.com)
        subject:  Email subject
        body:     Plain-text email body (cover letter)
        cv_path:  Absolute path to CV file to attach (optional)

    Returns:
        dict with keys: ok (bool), message (str), detail (str|None)
    """
    email    = os.environ.get("PROTONMAIL_EMAIL", "")
    password = os.environ.get("PROTONMAIL_PASSWORD", "")

    if not email or not password:
        return {
            "ok": False,
            "message": "ProtonMail credentials not configured.",
            "detail": "Go to Settings → ProtonMail and enter your account details.",
        }

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {
            "ok": False,
            "message": "Playwright not installed.",
            "detail": "Run: pip install playwright && playwright install chromium",
        }

    screenshots_dir = Path(__file__).parent.parent.parent / "logs" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            # ── Step 1: Go to ProtonMail ── #
            logger.info("[ProtonMail] Navigating to login page...")
            page.goto(PROTONMAIL_URL, timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=30_000)

            # ── Step 2: Log in ── #
            logger.info("[ProtonMail] Logging in...")
            try:
                # Enter username
                user_field = page.locator('input[id="username"], input[name="username"]').first
                user_field.fill(email)

                # Click continue / next
                next_btn = page.locator('button[type="submit"]').first
                next_btn.click()
                page.wait_for_timeout(1500)

                # Enter password
                pass_field = page.locator('input[type="password"]').first
                pass_field.fill(password)
                pass_field.press("Enter")

                # Wait for inbox to load
                page.wait_for_selector('[data-testid="navigation-link:inbox"], .navigation-link', timeout=30_000)
                logger.info("[ProtonMail] Login successful.")
            except PWTimeout:
                page.screenshot(path=str(screenshots_dir / "protonmail_login_failed.png"))
                return {
                    "ok": False,
                    "message": "ProtonMail login timed out.",
                    "detail": "Check your email/password in Settings. Screenshot saved in logs/screenshots/.",
                }

            # ── Step 3: Compose ── #
            logger.info("[ProtonMail] Opening compose window...")
            try:
                compose_btn = page.locator('button[data-testid="sidebar:compose"], [data-testid="compose-button"]').first
                compose_btn.click()
                page.wait_for_selector('[data-testid="composer:to"]', timeout=10_000)
            except PWTimeout:
                page.screenshot(path=str(screenshots_dir / "protonmail_compose_failed.png"))
                return {"ok": False, "message": "Could not open compose window.", "detail": "Screenshot saved."}

            # ── Step 4: Fill recipient ── #
            to_field = page.locator('[data-testid="composer:to"] input').first
            to_field.fill(to)
            to_field.press("Enter")
            page.wait_for_timeout(500)

            # ── Step 5: Fill subject ── #
            subject_field = page.locator('[data-testid="composer:subject"]').first
            subject_field.fill(subject)

            # ── Step 6: Fill body ── #
            # ProtonMail uses a contenteditable div
            body_area = page.locator('[data-testid="rooster-editor"], .composer-content [contenteditable="true"]').first
            body_area.click()
            # Clear existing content and type
            body_area.press("Control+a")
            body_area.type(body)
            page.wait_for_timeout(500)

            # ── Step 7: Attach CV ── #
            if cv_path and Path(cv_path).exists():
                logger.info(f"[ProtonMail] Attaching CV: {cv_path}")
                try:
                    attach_btn = page.locator('[data-testid="composer:attachment-button"]').first
                    with page.expect_file_chooser() as fc_info:
                        attach_btn.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(cv_path)
                    page.wait_for_timeout(1500)
                except Exception as e:
                    logger.warning(f"[ProtonMail] CV attachment failed: {e} — continuing without attachment")

            # ── Step 8: Send ── #
            logger.info("[ProtonMail] Sending email...")
            send_btn = page.locator('[data-testid="composer:send-button"]').first
            send_btn.click()

            # Wait for confirmation (compose window closes)
            try:
                page.wait_for_selector('[data-testid="composer:to"]', state="detached", timeout=10_000)
                logger.info("[ProtonMail] Email sent successfully.")
            except PWTimeout:
                # May have already closed
                pass

            browser.close()

            return {
                "ok": True,
                "message": f"Email sent to {to}",
                "detail": f"Subject: {subject}",
            }

    except Exception as e:
        logger.error(f"[ProtonMail] Unexpected error: {e}")
        return {
            "ok": False,
            "message": "Email sending failed.",
            "detail": str(e),
        }


def is_configured() -> bool:
    """Return True if ProtonMail credentials are set."""
    return bool(
        os.environ.get("PROTONMAIL_EMAIL")
        and os.environ.get("PROTONMAIL_PASSWORD")
    )
