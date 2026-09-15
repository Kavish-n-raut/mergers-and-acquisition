from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to backend/.env so it loads regardless of the process CWD
# (uvicorn is launched from the project root with --app-dir backend).
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="QuantumBlack M&A Deal OS", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    database_url: str = Field(default="sqlite:///./ma_deal_os.db", alias="DATABASE_URL")
    default_role: str = Field(default="analyst", alias="DEFAULT_ROLE")

    # Comma-separated list of allowed browser origins for CORS. A wildcard "*"
    # cannot be combined with credentialed requests, so we default to the local
    # Vite dev origins. Override via CORS_ORIGINS in .env for other deployments.
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    ai_provider: Literal["local", "anthropic", "groq"] = Field(default="local", alias="AI_PROVIDER")
    use_anthropic: bool = Field(default=False, alias="USE_ANTHROPIC")
    # Groq free LLM (OpenAI-compatible, https://console.groq.com). Fast + free tier.
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL"
    )
    anthropic_version: str = Field(default="2023-06-01", alias="ANTHROPIC_VERSION")
    local_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="LOCAL_EMBEDDING_MODEL"
    )
    finbert_model: str = Field(default="ProsusAI/finbert", alias="FINBERT_MODEL")

    # Finnhub free market-data API (https://finnhub.io — 60 calls/min free tier).
    finnhub_api_key: str | None = Field(default=None, alias="FINNHUB_API_KEY")
    # PatentsView / USPTO search API (free key from https://search.patentsview.org).
    patentsview_api_key: str | None = Field(default=None, alias="PATENTSVIEW_API_KEY")
    # USPTO Open Data Portal (data.uspto.gov) — free self-serve key; throttle-proof
    # official patent source. Preferred over Google Patents when set.
    uspto_api_key: str | None = Field(default=None, alias="USPTO_API_KEY")

    # Authentication (JWT). auth_enforced=False keeps the legacy x-user-role header
    # working for local dev/tests; set AUTH_ENFORCED=true to require a valid Bearer token.
    jwt_secret: str = Field(default="dev-insecure-secret-change-me", alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=10080, alias="JWT_EXPIRE_MINUTES")  # 7 days (override via JWT_EXPIRE_MINUTES env)
    auth_enforced: bool = Field(default=False, alias="AUTH_ENFORCED")
    demo_password: str = Field(default="changeme-demo", alias="DEMO_PASSWORD")

    synergy_npv_multiple: float = Field(default=5.0, alias="SYNERGY_NPV_MULTIPLE")
    pitchbook_output_dir: str = Field(default="generated_pitchbooks", alias="PITCHBOOK_OUTPUT_DIR")

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        placeholder_values = {
            "your_real_key",
            "your_real_key_here",
            "your_key_here",
            "replace_me",
            "changeme",
        }
        lowered = normalized.lower()
        if lowered in placeholder_values or lowered.startswith("your_"):
            return None

        # Keep key optional and non-blocking for local MVP mode. Runtime provider checks
        # decide whether Anthropic should actually be used.
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
