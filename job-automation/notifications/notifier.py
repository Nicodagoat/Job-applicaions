"""
Notification service.
Supports Telegram (primary), email fallback.
Sends alerts when manual input is required, high-match jobs found, etc.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import requests
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
with open(_SETTINGS_PATH) as _f:
    _SETTINGS = yaml.safe_load(_f)


# --------------------------------------------------------------------------- #
# Event types                                                                  #
# --------------------------------------------------------------------------- #

class NotificationEvent:
    MANUAL_INPUT_REQUIRED = "manual_input_required"
    APPLICATION_SUBMITTED  = "application_submitted"
    APPLICATION_FAILED     = "application_failed"
    HIGH_MATCH_JOB         = "high_match_job_found"
    INTERVIEW_INVITATION   = "interview_invitation"
    REJECTION_RECEIVED     = "rejection_received"
    DAILY_SUMMARY          = "daily_summary"


# --------------------------------------------------------------------------- #
# Telegram                                                                     #
# --------------------------------------------------------------------------- #

class TelegramNotifier:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("[Telegram] Bot token or chat ID not configured.")
            return False
        try:
            response = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"[Telegram] Send failed: {e}")
            return False


# --------------------------------------------------------------------------- #
# Email                                                                        #
# --------------------------------------------------------------------------- #

class EmailNotifier:
    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASSWORD", "")

    def send(self, subject: str, body: str, to: Optional[str] = None) -> bool:
        if not self.user or not self.password:
            logger.warning("[Email] SMTP credentials not configured.")
            return False
        recipient = to or self.user
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.user
            msg["To"] = recipient
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(self.host, self.port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, recipient, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"[Email] Send failed: {e}")
            return False


# --------------------------------------------------------------------------- #
# Main Notifier                                                                #
# --------------------------------------------------------------------------- #

class Notifier:
    """
    High-level notification dispatcher.
    Tries Telegram first, falls back to email.
    """

    def __init__(self):
        self.settings = _SETTINGS["notifications"]
        self.telegram = TelegramNotifier()
        self.email = EmailNotifier()
        self.enabled_events = set(self.settings.get("events", []))

    def _should_send(self, event: str) -> bool:
        return (
            self.settings.get("enabled", True) and
            event in self.enabled_events
        )

    def _format_job_message(
        self,
        event: str,
        job_title: str,
        company: str,
        url: Optional[str],
        action: Optional[str],
        score: Optional[float] = None,
    ) -> str:
        emoji_map = {
            NotificationEvent.MANUAL_INPUT_REQUIRED: "⚠️",
            NotificationEvent.APPLICATION_SUBMITTED: "✅",
            NotificationEvent.APPLICATION_FAILED: "❌",
            NotificationEvent.HIGH_MATCH_JOB: "🎯",
            NotificationEvent.INTERVIEW_INVITATION: "🎉",
            NotificationEvent.REJECTION_RECEIVED: "📭",
        }
        emoji = emoji_map.get(event, "📢")
        score_str = f"  • Match score: *{score:.0f}/100*\n" if score else ""
        action_str = f"  • *Action needed:* {action}\n" if action else ""
        url_str = f"  • [View Job]({url})\n" if url else ""

        return (
            f"{emoji} *Job Application Update*\n\n"
            f"  • *{job_title}* at *{company}*\n"
            f"{score_str}"
            f"{action_str}"
            f"{url_str}"
            f"\n_Platform: Job Application Automation_"
        )

    def notify_manual_input(
        self,
        job_title: str,
        company: str,
        url: Optional[str],
        action: str,
    ) -> None:
        if not self._should_send(NotificationEvent.MANUAL_INPUT_REQUIRED):
            return
        msg = self._format_job_message(
            NotificationEvent.MANUAL_INPUT_REQUIRED,
            job_title, company, url, action
        )
        self._dispatch(msg, subject=f"[ACTION NEEDED] {job_title} @ {company}")

    def notify_high_match(
        self,
        job_title: str,
        company: str,
        url: Optional[str],
        score: float,
    ) -> None:
        if not self._should_send(NotificationEvent.HIGH_MATCH_JOB):
            return
        msg = self._format_job_message(
            NotificationEvent.HIGH_MATCH_JOB,
            job_title, company, url,
            action="Review and approve application",
            score=score,
        )
        self._dispatch(msg, subject=f"[HIGH MATCH] {job_title} @ {company} ({score:.0f}%)")

    def notify_submitted(self, job_title: str, company: str, url: Optional[str]) -> None:
        if not self._should_send(NotificationEvent.APPLICATION_SUBMITTED):
            return
        msg = self._format_job_message(
            NotificationEvent.APPLICATION_SUBMITTED,
            job_title, company, url, action=None
        )
        self._dispatch(msg, subject=f"[APPLIED] {job_title} @ {company}")

    def notify_interview(self, job_title: str, company: str, url: Optional[str]) -> None:
        if not self._should_send(NotificationEvent.INTERVIEW_INVITATION):
            return
        msg = self._format_job_message(
            NotificationEvent.INTERVIEW_INVITATION,
            job_title, company, url,
            action="Check your email and respond to interview invitation",
        )
        self._dispatch(msg, subject=f"[INTERVIEW!] {job_title} @ {company}")

    def notify_daily_summary(self, stats: dict) -> None:
        if not self._should_send(NotificationEvent.DAILY_SUMMARY):
            return
        msg = (
            f"📊 *Daily Job Search Summary*\n\n"
            f"  • New jobs found: *{stats.get('new_jobs', 0)}*\n"
            f"  • Applications submitted: *{stats.get('submitted', 0)}*\n"
            f"  • Pending review: *{stats.get('pending', 0)}*\n"
            f"  • Interviews invited: *{stats.get('interviews', 0)}*\n"
        )
        self._dispatch(msg, subject="[DAILY SUMMARY] Job Search Update")

    def _dispatch(self, message: str, subject: str) -> None:
        sent = self.telegram.send(message)
        if not sent:
            # Fallback to email
            plain = message.replace("*", "").replace("_", "").replace("[", "").replace("]", "")
            self.email.send(subject=subject, body=plain)
