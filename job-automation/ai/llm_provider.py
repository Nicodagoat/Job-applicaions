"""
Unified LLM provider — auto-detects the best available AI.

Priority order (cloud-first, no local hardware needed):
  1. DeepSeek — very cheap cloud API, excellent quality (set DEEPSEEK_API_KEY)
  2. Groq     — free cloud API tier, LLaMA 3.1 70B (set GROQ_API_KEY)
  3. OpenAI   — optional paid fallback (set OPENAI_API_KEY)
  4. Ollama   — local LLaMA, runs on your machine (optional, needs GPU/RAM)

Recommended: Sign up at https://platform.deepseek.com (cheapest option)
or https://console.groq.com (completely free tier)
Then add the API key in the Settings page — no terminal needed.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Provider detection                                                           #
# --------------------------------------------------------------------------- #

OLLAMA_BASE_URL  = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.environ.get("OLLAMA_MODEL", "llama3.1")

GROQ_API_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL       = "llama-3.3-70b-versatile"

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL   = "deepseek-chat"


def _deepseek_available() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def _groq_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _openai_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _ollama_available() -> bool:
    """Return True if Ollama is running and the model is available."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return any(OLLAMA_MODEL.split(":")[0] in m for m in models)
    except Exception:
        pass
    return False


def get_provider_info() -> dict:
    """Return which AI provider is active and its details."""
    if _deepseek_available():
        return {"name": "DeepSeek", "model": DEEPSEEK_MODEL, "free": False, "local": False}
    if _groq_available():
        return {"name": "Groq", "model": GROQ_MODEL, "free": True, "local": False}
    if _openai_available():
        return {"name": "OpenAI", "model": "gpt-4o-mini", "free": False, "local": False}
    if _ollama_available():
        return {"name": "Ollama (local)", "model": OLLAMA_MODEL, "free": True, "local": True}
    return {"name": "none", "model": None, "free": False, "local": False}


# --------------------------------------------------------------------------- #
# Core chat function                                                           #
# --------------------------------------------------------------------------- #

def chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    expect_json: bool = False,
) -> str:
    """
    Send a chat request to the best available free AI provider.
    Returns the response text.
    Raises RuntimeError if no provider is configured.
    """
    if _deepseek_available():
        return _deepseek_chat(system_prompt, user_prompt, temperature, max_tokens, expect_json)
    if _groq_available():
        return _groq_chat(system_prompt, user_prompt, temperature, max_tokens, expect_json)
    if _openai_available():
        return _openai_chat(system_prompt, user_prompt, temperature, max_tokens, expect_json)
    if _ollama_available():
        return _ollama_chat(system_prompt, user_prompt, temperature, max_tokens, expect_json)

    raise RuntimeError(
        "No AI provider configured. "
        "Go to Settings in the dashboard and add a free Groq key or a DeepSeek key."
    )


# --------------------------------------------------------------------------- #
# Ollama                                                                       #
# --------------------------------------------------------------------------- #

def _ollama_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if expect_json:
        payload["format"] = "json"

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120,  # Local models can be slow
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.RequestException as e:
        logger.error(f"[Ollama] Request failed: {e}")
        raise RuntimeError(f"Ollama error: {e}")


# --------------------------------------------------------------------------- #
# DeepSeek (very affordable cloud API, OpenAI-compatible)                     #
# --------------------------------------------------------------------------- #

def _deepseek_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> str:
    headers = {
        "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        logger.error(f"[DeepSeek] Request failed: {e}")
        raise RuntimeError(f"DeepSeek error: {e}")


# --------------------------------------------------------------------------- #
# Groq (free API)                                                              #
# --------------------------------------------------------------------------- #

def _groq_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> str:
    headers = {
        "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        logger.error(f"[Groq] Request failed: {e}")
        raise RuntimeError(f"Groq error: {e}")


# --------------------------------------------------------------------------- #
# OpenAI (paid fallback)                                                       #
# --------------------------------------------------------------------------- #

def _openai_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        kwargs = dict(
            model="gpt-4o-mini",
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenAI error: {e}")


# --------------------------------------------------------------------------- #
# JSON helper                                                                  #
# --------------------------------------------------------------------------- #

def chat_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict:
    """
    Like chat() but always returns a parsed dict.
    Falls back to extracting JSON from fenced code blocks if needed.
    """
    raw = chat(system_prompt, user_prompt, temperature=temperature, expect_json=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try to find first { ... } block
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger.warning(f"[LLM] Could not parse JSON response: {raw[:200]}")
        return {}
