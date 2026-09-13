from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Absolute path to backend/.env (uvicorn runs from the project root).
_ENV_FILE = str(Path(__file__).resolve().parents[2] / ".env")

AIProvider = Literal["local", "anthropic", "groq"]


def _parse_bool_env(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}


def resolve_ai_provider() -> AIProvider:
    load_dotenv(dotenv_path=_ENV_FILE, override=False)
    provider = os.getenv("AI_PROVIDER", "local").strip().lower()
    use_anthropic = _parse_bool_env(os.getenv("USE_ANTHROPIC", "false"))
    if provider == "groq":
        return "groq"
    if use_anthropic or provider == "anthropic":
        return "anthropic"
    return "local"


def get_groq_api_key() -> str | None:
    load_dotenv(dotenv_path=_ENV_FILE, override=False)
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    return key or None


def has_valid_groq_key() -> bool:
    key = get_groq_api_key()
    return bool(key and not key.lower().startswith("your_"))


def should_use_groq() -> bool:
    return resolve_ai_provider() == "groq" and has_valid_groq_key()


def get_anthropic_api_key() -> str | None:
    load_dotenv(dotenv_path=_ENV_FILE, override=False)
    key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        return None
    return key


def has_valid_anthropic_key() -> bool:
    key = get_anthropic_api_key()
    return bool(key and key.startswith("sk-ant-"))


def should_use_anthropic() -> bool:
    return resolve_ai_provider() == "anthropic" and has_valid_anthropic_key()

