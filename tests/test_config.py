import importlib

import app.core.config as config_module


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@db:5432/m4")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("TELEGRAM_API_ID", "424242")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash-abc")
    monkeypatch.setenv("TELETHON_STRING_SESSION", "sess-xyz")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:bot-token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-1009999")

    reloaded = importlib.reload(config_module)
    settings = reloaded.Settings(_env_file=None)

    assert settings.ENVIRONMENT == "prod"
    assert settings.DATABASE_URL == "postgresql+psycopg2://u:p@db:5432/m4"
    assert settings.REDIS_URL == "redis://redis:6379/1"
    assert settings.OPENAI_API_KEY.get_secret_value() == "sk-test-123"
    assert settings.OPENAI_MODEL == "gpt-4o-mini"
    assert settings.OPENAI_TIMEOUT == 30
    assert settings.OPENAI_BASE_URL is None
    assert settings.MODERATION_ENABLED is True
    assert settings.TELEGRAM_API_ID == 424242
    assert settings.TELEGRAM_API_HASH.get_secret_value() == "hash-abc"
    assert settings.TELETHON_STRING_SESSION.get_secret_value() == "sess-xyz"
    assert settings.TELEGRAM_BOT_TOKEN.get_secret_value() == "111:bot-token"
    assert settings.TELEGRAM_CHANNEL_ID == -1009999
    assert settings.ALLOWED_LANGUAGES == ["uk", "en"]
    assert settings.DEDUP_TTL_SECONDS == 604800
    assert settings.KEYWORD_MATCH_MODE == "any"
    assert settings.POST_MAX_LEN == 4096


def test_prod_raises_on_empty_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    # Clear any ambient secrets (CI sets OPENAI_API_KEY/TELEGRAM_* in its env) so
    # prod validation actually sees them empty and raises.
    for var in (
        "OPENAI_API_KEY",
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELETHON_STRING_SESSION",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHANNEL_ID",
    ):
        monkeypatch.delenv(var, raising=False)

    import pytest

    with pytest.raises(ValueError):
        import importlib as _il

        _il.reload(config_module)
        config_module.Settings(_env_file=None)


def test_local_with_empty_secrets_does_not_raise(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")

    reloaded = importlib.reload(config_module)
    settings = reloaded.Settings(_env_file=None)  # must not raise
    assert settings.ENVIRONMENT == "local"


def test_openai_base_url_and_moderation_toggle(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("MODERATION_ENABLED", "false")

    reloaded = importlib.reload(config_module)
    settings = reloaded.Settings(_env_file=None)

    assert settings.OPENAI_BASE_URL == "https://openrouter.ai/api/v1"
    assert settings.MODERATION_ENABLED is False


def test_secrets_are_not_plain_in_repr(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("TELETHON_STRING_SESSION", "s")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "1")

    reloaded = importlib.reload(config_module)
    settings = reloaded.Settings(_env_file=None)

    assert "sk-secret" not in repr(settings.OPENAI_API_KEY)
