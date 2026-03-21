"""
Profile service — reads and writes config/profile.yaml.
Powers the My Info page so all personal details are editable from the browser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROFILE_PATH = Path(__file__).parent.parent.parent / "config" / "profile.yaml"


def read_profile() -> dict:
    """Return the full profile as a dict."""
    with open(PROFILE_PATH) as f:
        return yaml.safe_load(f) or {}


def save_profile(data: dict) -> None:
    """
    Overwrite profile.yaml with the supplied data dict.
    The frontend sends back the full profile, we write it as-is.
    """
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False)


def update_profile_section(section: str, data: Any) -> None:
    """Update a single top-level section in profile.yaml."""
    profile = read_profile()
    profile[section] = data
    save_profile(profile)
