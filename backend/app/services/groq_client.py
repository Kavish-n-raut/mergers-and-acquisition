"""Groq free LLM client (OpenAI-compatible chat completions).

A free, fast alternative to paid GPT-4/Claude for the platform's text-generation
needs (explanations, drafting, structured extraction). Free tier from
https://console.groq.com. Set GROQ_API_KEY to enable.

Verified contract (April 2026): POST https://api.groq.com/openai/v1/chat/completions
  headers: Authorization: Bearer <key>
  body: {model, messages:[{role,content}], temperature, max_tokens, response_format?}
  -> {choices:[{message:{content}}], ...}
Default model: llama-3.3-70b-versatile.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from app.core.config import get_settings

CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT = 45


class GroqError(ValueError):
    pass


class GroqConfigurationError(GroqError):
    pass


def is_configured() -> bool:
    key = get_settings().groq_api_key
    return bool(key and key.strip() and not key.strip().lower().startswith("your_"))


def _post(messages: list[dict[str, str]], *, temperature: float, max_tokens: int, json_mode: bool) -> str:
    if not is_configured():
        raise GroqConfigurationError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com and add it to backend/.env."
        )
    settings = get_settings()
    body: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.groq_api_key.strip()}", "Content-Type": "application/json"}
    try:
        resp = requests.post(CHAT_URL, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise GroqError(f"Groq request failed: {exc}") from exc
    if resp.status_code in (401, 403):
        raise GroqConfigurationError("Groq rejected the API key. Check GROQ_API_KEY.")
    if resp.status_code == 429:
        raise GroqError("Groq rate limit hit (429). Slow down or upgrade the free tier.")
    if resp.status_code >= 400:
        raise GroqError(f"Groq request failed ({resp.status_code}): {resp.text[:200]}")
    try:
        payload = resp.json()
        return payload["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        raise GroqError(f"Unexpected Groq response shape: {exc}") from exc


def generate_text(prompt: str, *, system: str = "You are a precise M&A analyst.", temperature: float = 0.2, max_tokens: int = 1024) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    return _post(messages, temperature=temperature, max_tokens=max_tokens, json_mode=False)


def generate_json(prompt: str, *, system: str = "You return only valid JSON.", temperature: float = 0.0, max_tokens: int = 1600) -> dict[str, Any]:
    system = system + " Respond with a single JSON object and nothing else."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    raw = _post(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GroqError(f"Groq did not return valid JSON: {exc}") from exc


def check_connectivity() -> dict[str, Any]:
    content = generate_text("Reply with the single word: ok", max_tokens=5)
    return {"provider": "groq", "model": get_settings().groq_model, "reply": content.strip()[:20]}
