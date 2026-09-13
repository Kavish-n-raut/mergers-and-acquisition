from __future__ import annotations

import json
import os
from typing import Any, TypeVar

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
SUPPORTED_SCHEMA_KEYS_TO_DROP = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "multipleOf",
    "minItems",
    "maxItems",
    "minProperties",
    "maxProperties",
}


class AnthropicClientError(ValueError):
    pass


class AnthropicConfigurationError(AnthropicClientError):
    pass


class AnthropicRequestError(AnthropicClientError):
    def __init__(self, *, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Anthropic Messages API request failed ({status_code}): {detail}")


class AnthropicAuthenticationError(AnthropicRequestError):
    pass


class AnthropicResponseError(AnthropicClientError):
    pass


SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


def _sanitize_json_schema(node: Any) -> Any:
    if isinstance(node, dict):
        sanitized: dict[str, Any] = {}
        for key, value in node.items():
            if key in SUPPORTED_SCHEMA_KEYS_TO_DROP:
                continue
            sanitized[key] = _sanitize_json_schema(value)
        if sanitized.get("type") == "object" and "additionalProperties" not in sanitized:
            sanitized["additionalProperties"] = False
        return sanitized
    if isinstance(node, list):
        return [_sanitize_json_schema(item) for item in node]
    return node


def _extract_json_text(response_payload: dict[str, Any]) -> str:
    content = response_payload.get("content", [])
    if not isinstance(content, list):
        raise AnthropicResponseError("Anthropic response content is not a list.")

    text_blocks = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "\n".join(part for part in text_blocks if isinstance(part, str)).strip()
    if not text:
        raise AnthropicResponseError("Anthropic response did not include any text blocks.")
    return text


def _best_effort_json_snippet(text: str) -> str:
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    raise AnthropicResponseError("Model response did not contain valid JSON.")


def _post_messages_request(
    *,
    api_key: str,
    anthropic_version: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": anthropic_version,
        "content-type": "application/json",
    }
    response = requests.post(
        ANTHROPIC_MESSAGES_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )
    if response.status_code >= 400:
        detail = response.text
        try:
            error_json = response.json()
            if isinstance(error_json, dict):
                error_block = error_json.get("error")
                if isinstance(error_block, dict):
                    detail = error_block.get("message", detail)
        except Exception:
            pass
        if response.status_code in (401, 403):
            raise AnthropicAuthenticationError(status_code=response.status_code, detail=detail)
        raise AnthropicRequestError(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except Exception as exc:
        raise AnthropicResponseError(f"Anthropic returned non-JSON response: {exc}") from exc


def generate_structured_output(
    *,
    output_model: type[SchemaModelT],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    model: str | None = None,
) -> SchemaModelT:
    load_dotenv(override=False)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnthropicConfigurationError("ANTHROPIC_API_KEY is missing.")

    model_name = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    anthropic_version = os.getenv("ANTHROPIC_VERSION", DEFAULT_ANTHROPIC_VERSION)
    schema = _sanitize_json_schema(output_model.model_json_schema())

    base_payload = {
        "model": model_name,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    schema_payload = {
        **base_payload,
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    }

    try:
        response_payload = _post_messages_request(
            api_key=api_key,
            anthropic_version=anthropic_version,
            payload=schema_payload,
        )
        json_text = _extract_json_text(response_payload)
        return output_model.model_validate_json(_best_effort_json_snippet(json_text))
    except AnthropicRequestError as exc:
        lower_detail = exc.detail.lower()
        can_fallback = exc.status_code == 400 and any(
            marker in lower_detail for marker in ("output_config", "json_schema", "schema")
        )
        if not can_fallback:
            raise
    except (AnthropicResponseError, ValidationError):
        pass

    fallback_prompt = (
        f"{user_prompt}\n\n"
        "Return ONLY valid JSON that matches this schema exactly (no markdown, no prose):\n"
        f"{json.dumps(schema, ensure_ascii=True)}"
    )
    fallback_payload = {
        **base_payload,
        "messages": [{"role": "user", "content": fallback_prompt}],
    }
    response_payload = _post_messages_request(
        api_key=api_key,
        anthropic_version=anthropic_version,
        payload=fallback_payload,
    )
    json_text = _extract_json_text(response_payload)
    return output_model.model_validate_json(_best_effort_json_snippet(json_text))


def check_anthropic_connectivity(model: str | None = None) -> dict[str, str]:
    load_dotenv(override=False)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnthropicConfigurationError("ANTHROPIC_API_KEY is missing.")

    model_name = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    anthropic_version = os.getenv("ANTHROPIC_VERSION", DEFAULT_ANTHROPIC_VERSION)
    payload = {
        "model": model_name,
        "max_tokens": 1,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": "healthcheck"}],
    }
    response_payload = _post_messages_request(
        api_key=api_key,
        anthropic_version=anthropic_version,
        payload=payload,
    )
    request_id = str(response_payload.get("id", ""))
    return {
        "provider": "anthropic",
        "model": model_name,
        "request_id": request_id,
    }
