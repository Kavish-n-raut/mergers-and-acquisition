from app.core.config import Settings


def test_anthropic_key_accepts_blank_value():
    settings = Settings(ANTHROPIC_API_KEY="")
    assert settings.anthropic_api_key is None


def test_anthropic_key_accepts_placeholder_value():
    settings = Settings(ANTHROPIC_API_KEY="your_real_key")
    assert settings.anthropic_api_key is None


def test_anthropic_key_allows_non_empty_value_for_optional_mode():
    settings = Settings(ANTHROPIC_API_KEY="invalid-key")
    assert settings.anthropic_api_key == "invalid-key"


def test_default_ai_provider_is_local():
    # _env_file=None skips loading backend/.env so we test the field's own default,
    # independent of whatever provider is configured in the real environment.
    settings = Settings(_env_file=None)
    assert settings.ai_provider == "local"
