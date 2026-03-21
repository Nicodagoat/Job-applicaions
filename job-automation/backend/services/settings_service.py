"""
Settings service — reads and writes config/.env and config/settings.yaml.

This powers the in-browser Settings page so the user never needs to
touch the terminal to configure the platform.
"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any

import yaml

ENV_PATH      = Path(__file__).parent.parent.parent / "config" / ".env"
SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"

# Fields that are sensitive — masked in API responses
_SECRET_FIELDS = {
    "GROQ_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
    "ADZUNA_APP_KEY", "REED_API_KEY",
    "LINKEDIN_PASSWORD", "PROTONMAIL_PASSWORD",
    "TELEGRAM_BOT_TOKEN", "SECRET_KEY",
    "SMTP_PASSWORD", "DB_PASSWORD",
}


# --------------------------------------------------------------------------- #
# .env reader / writer                                                         #
# --------------------------------------------------------------------------- #

def read_env() -> dict[str, str]:
    """Read all key=value pairs from config/.env."""
    result: dict[str, str] = {}
    if not ENV_PATH.exists():
        return result
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def write_env_keys(updates: dict[str, str]) -> None:
    """
    Update specific keys in config/.env, preserving all other content.
    Creates the file if it doesn't exist.
    """
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Read existing content
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()
    else:
        lines = []

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    # Append keys that weren't already in the file
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    # Reload into os.environ immediately
    for key, value in updates.items():
        os.environ[key] = value

    ENV_PATH.write_text("\n".join(new_lines) + "\n")


def mask_value(key: str, value: str) -> str:
    """Return a masked version of a sensitive value for display."""
    if key not in _SECRET_FIELDS or not value:
        return value
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "••••••••" + value[-4:]


# --------------------------------------------------------------------------- #
# Settings YAML reader / writer                                                #
# --------------------------------------------------------------------------- #

def read_settings() -> dict:
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def update_settings(path: list[str], value: Any) -> None:
    """
    Update a nested key in settings.yaml.
    path = ["safety", "dry_run"], value = False
    """
    settings = read_settings()
    node = settings
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    with open(SETTINGS_PATH, "w") as f:
        yaml.dump(settings, f, default_flow_style=False, allow_unicode=True)


# --------------------------------------------------------------------------- #
# High-level get/set for the Settings API                                     #
# --------------------------------------------------------------------------- #

def get_all_settings() -> dict:
    """
    Return all configurable settings for the Settings page.
    Sensitive values are masked.
    """
    env    = read_env()
    setts  = read_settings()
    safety = setts.get("safety", {})
    app_cfg = setts.get("application", {})

    def e(key: str) -> str:
        return mask_value(key, env.get(key, ""))

    return {
        "ai": {
            "groq_api_key":      e("GROQ_API_KEY"),
            "deepseek_api_key":  e("DEEPSEEK_API_KEY"),
            "openai_api_key":    e("OPENAI_API_KEY"),
            "active_provider":   _detect_active_provider(env),
        },
        "linkedin": {
            "email":    env.get("LINKEDIN_EMAIL", ""),
            "password": e("LINKEDIN_PASSWORD"),
            "connected": bool(env.get("LINKEDIN_EMAIL") and env.get("LINKEDIN_PASSWORD")),
        },
        "protonmail": {
            "email":    env.get("PROTONMAIL_EMAIL", ""),
            "password": e("PROTONMAIL_PASSWORD"),
            "connected": bool(env.get("PROTONMAIL_EMAIL") and env.get("PROTONMAIL_PASSWORD")),
        },
        "job_sources": {
            "adzuna_app_id":  env.get("ADZUNA_APP_ID", ""),
            "adzuna_app_key": e("ADZUNA_APP_KEY"),
            "reed_api_key":   e("REED_API_KEY"),
            "adzuna_ok":      bool(env.get("ADZUNA_APP_ID") and env.get("ADZUNA_APP_KEY")),
            "reed_ok":        bool(env.get("REED_API_KEY")),
        },
        "telegram": {
            "bot_token": e("TELEGRAM_BOT_TOKEN"),
            "chat_id":   env.get("TELEGRAM_CHAT_ID", ""),
            "connected": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")),
        },
        "rules": {
            "dry_run":           safety.get("dry_run", True),
            "human_approval":    safety.get("human_approval_required", True),
            "max_daily_apps":    safety.get("max_daily_applications", 10),
            "min_match_score":   setts.get("application", {}).get("min_match_score", 65),
        },
    }


def save_settings(section: str, data: dict) -> None:
    """
    Save settings for a given section.
    Routes to .env or settings.yaml as appropriate.
    """
    env_map = {
        "ai": {
            "groq_api_key":     "GROQ_API_KEY",
            "deepseek_api_key": "DEEPSEEK_API_KEY",
            "openai_api_key":   "OPENAI_API_KEY",
        },
        "linkedin": {
            "email":    "LINKEDIN_EMAIL",
            "password": "LINKEDIN_PASSWORD",
        },
        "protonmail": {
            "email":    "PROTONMAIL_EMAIL",
            "password": "PROTONMAIL_PASSWORD",
        },
        "job_sources": {
            "adzuna_app_id":  "ADZUNA_APP_ID",
            "adzuna_app_key": "ADZUNA_APP_KEY",
            "reed_api_key":   "REED_API_KEY",
        },
        "telegram": {
            "bot_token": "TELEGRAM_BOT_TOKEN",
            "chat_id":   "TELEGRAM_CHAT_ID",
        },
    }

    if section in env_map:
        updates = {}
        for field, env_key in env_map[section].items():
            if field in data and data[field] not in ("", None):
                # Don't overwrite with masked placeholder
                val = data[field]
                if "••" not in str(val):
                    updates[env_key] = str(val)
        if updates:
            write_env_keys(updates)

    elif section == "rules":
        if "dry_run" in data:
            update_settings(["safety", "dry_run"], bool(data["dry_run"]))
        if "human_approval" in data:
            update_settings(["safety", "human_approval_required"], bool(data["human_approval"]))
        if "max_daily_apps" in data:
            update_settings(["safety", "max_daily_applications"], int(data["max_daily_apps"]))
        if "min_match_score" in data:
            update_settings(["application", "min_match_score"], int(data["min_match_score"]))


def _detect_active_provider(env: dict) -> str:
    if env.get("DEEPSEEK_API_KEY"):
        return "DeepSeek"
    if env.get("GROQ_API_KEY"):
        return "Groq"
    if env.get("OPENAI_API_KEY"):
        return "OpenAI"
    return "none"
