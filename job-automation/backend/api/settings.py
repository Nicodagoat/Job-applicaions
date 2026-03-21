"""
Settings API — exposes in-browser configuration so you never need the terminal.
"""

from __future__ import annotations

import os
import logging
from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.settings_service import (
    get_all_settings,
    save_settings,
    read_env,
    write_env_keys,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Request / response models                                                   #
# --------------------------------------------------------------------------- #

class SectionPayload(BaseModel):
    data: dict[str, Any]


class TestResult(BaseModel):
    ok: bool
    message: str
    detail: str | None = None


# --------------------------------------------------------------------------- #
# GET / POST settings                                                         #
# --------------------------------------------------------------------------- #

@router.get("")
def get_settings():
    """Return all configurable settings (sensitive values are masked)."""
    try:
        return get_all_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{section}")
def save_section(section: str, payload: SectionPayload):
    """
    Save a settings section.
    section = ai | linkedin | protonmail | job_sources | telegram | rules
    """
    valid = {"ai", "linkedin", "protonmail", "job_sources", "telegram", "rules"}
    if section not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown section: {section}")
    try:
        save_settings(section, payload.data)
        return {"ok": True, "message": "Settings saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
# Test / connection endpoints                                                  #
# --------------------------------------------------------------------------- #

@router.post("/test/ai", response_model=TestResult)
def test_ai():
    """Test whichever AI provider is currently configured."""
    try:
        from ai.llm_provider import get_provider_info, chat
        info = get_provider_info()
        if info["name"] == "none":
            return TestResult(ok=False, message="No AI provider configured.",
                              detail="Add a DeepSeek, Groq, or OpenAI API key above and save.")
        # Quick ping
        reply = chat(
            system_prompt="You are a helpful assistant. Reply only with OK.",
            user_prompt="Say OK.",
            max_tokens=5,
        )
        return TestResult(
            ok=True,
            message=f"{info['name']} is working.",
            detail=f"Model: {info['model']} · Response: {reply[:40]}",
        )
    except Exception as e:
        return TestResult(ok=False, message="AI test failed.", detail=str(e))


@router.post("/test/telegram", response_model=TestResult)
def test_telegram():
    """Send a test Telegram message."""
    env = read_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or env.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return TestResult(ok=False, message="Telegram not configured.",
                          detail="Fill in Bot Token and Chat ID and save first.")
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": "✅ Your Job Platform is connected to Telegram!",
        }, timeout=10)
        if r.status_code == 200:
            return TestResult(ok=True, message="Test message sent to Telegram!")
        return TestResult(ok=False, message="Telegram API error.",
                          detail=r.json().get("description", r.text[:200]))
    except Exception as e:
        return TestResult(ok=False, message="Connection failed.", detail=str(e))


@router.post("/test/adzuna", response_model=TestResult)
def test_adzuna():
    """Verify Adzuna API credentials."""
    env = read_env()
    app_id  = os.environ.get("ADZUNA_APP_ID")  or env.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY") or env.get("ADZUNA_APP_KEY", "")

    if not app_id or not app_key:
        return TestResult(ok=False, message="Adzuna not configured.",
                          detail="Enter your App ID and App Key and save.")
    try:
        url = (f"https://api.adzuna.com/v1/api/jobs/gb/search/1"
               f"?app_id={app_id}&app_key={app_key}&results_per_page=1&what=sustainability")
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            count = r.json().get("count", "?")
            return TestResult(ok=True, message=f"Adzuna connected! ({count} jobs available)")
        return TestResult(ok=False, message="Adzuna rejected the credentials.",
                          detail=f"HTTP {r.status_code}")
    except Exception as e:
        return TestResult(ok=False, message="Connection failed.", detail=str(e))


@router.post("/test/reed", response_model=TestResult)
def test_reed():
    """Verify Reed API credentials."""
    env = read_env()
    api_key = os.environ.get("REED_API_KEY") or env.get("REED_API_KEY", "")

    if not api_key:
        return TestResult(ok=False, message="Reed not configured.",
                          detail="Enter your Reed API key and save.")
    try:
        r = requests.get(
            "https://www.reed.co.uk/api/1.0/search?keywords=sustainability&resultsToTake=1",
            auth=(api_key, ""),
            timeout=10,
        )
        if r.status_code == 200:
            return TestResult(ok=True, message="Reed API connected!")
        return TestResult(ok=False, message="Reed rejected the API key.",
                          detail=f"HTTP {r.status_code}")
    except Exception as e:
        return TestResult(ok=False, message="Connection failed.", detail=str(e))


@router.post("/test/protonmail", response_model=TestResult)
def test_protonmail():
    """
    Verify ProtonMail credentials by checking they are saved.
    Full login test happens when actually sending an email via Playwright.
    """
    env = read_env()
    email    = os.environ.get("PROTONMAIL_EMAIL")    or env.get("PROTONMAIL_EMAIL", "")
    password = os.environ.get("PROTONMAIL_PASSWORD") or env.get("PROTONMAIL_PASSWORD", "")

    if not email or not password:
        return TestResult(ok=False, message="ProtonMail not configured.",
                          detail="Enter your ProtonMail address and password and save.")

    # Check credentials are syntactically plausible
    if "@" not in email:
        return TestResult(ok=False, message="Invalid email address.")

    return TestResult(
        ok=True,
        message="ProtonMail credentials saved.",
        detail=(
            f"Account: {email}. "
            "The platform will use these when sending email applications."
        ),
    )


@router.post("/test/linkedin", response_model=TestResult)
def test_linkedin():
    """
    Verify LinkedIn credentials are saved.
    Note: full LinkedIn login is handled by Playwright during form submission.
    """
    env = read_env()
    email    = os.environ.get("LINKEDIN_EMAIL")    or env.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD") or env.get("LINKEDIN_PASSWORD", "")

    if not email or not password:
        return TestResult(ok=False, message="LinkedIn not configured.",
                          detail="Enter your LinkedIn email and password and save.")

    if "@" not in email:
        return TestResult(ok=False, message="Invalid email address.")

    return TestResult(
        ok=True,
        message="LinkedIn credentials saved.",
        detail=(
            f"Account: {email}. "
            "The platform will use these to auto-fill LinkedIn Easy Apply forms."
        ),
    )
