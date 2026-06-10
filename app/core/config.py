from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["local", "prod"] = "local"

    DATABASE_URL: str = "sqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 30
    # Optional OpenAI-compatible endpoint (e.g. OpenRouter: https://openrouter.ai/api/v1).
    # None -> the default OpenAI API.
    OPENAI_BASE_URL: str | None = None
    # OpenAI moderation gate. Disable for OpenAI-compatible providers (OpenRouter)
    # that don't expose a /moderations endpoint.
    MODERATION_ENABLED: bool = True

    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: SecretStr = SecretStr("")
    TELETHON_STRING_SESSION: SecretStr = SecretStr("")
    TELEGRAM_BOT_TOKEN: SecretStr = SecretStr("")
    TELEGRAM_CHANNEL_ID: int = 0

    ALLOWED_LANGUAGES: list[str] = ["uk", "en"]
    KEYWORD_MATCH_MODE: Literal["any", "all"] = "any"
    POST_MAX_LEN: int = 4096
    # Max items processed per source per parse (newest first). Bounds the first-run
    # backfill of large feeds and per-cycle volume so generation/publishing can't flood.
    MAX_ITEMS_PER_PARSE: int = 25

    @model_validator(mode="after")
    def _require_secrets_in_prod(self) -> "Settings":
        if self.ENVIRONMENT == "prod":
            empty = [
                name
                for name, val in [
                    ("OPENAI_API_KEY", self.OPENAI_API_KEY),
                    ("TELEGRAM_API_HASH", self.TELEGRAM_API_HASH),
                    ("TELETHON_STRING_SESSION", self.TELETHON_STRING_SESSION),
                    ("TELEGRAM_BOT_TOKEN", self.TELEGRAM_BOT_TOKEN),
                ]
                if not val.get_secret_value()
            ] + [
                name
                for name, val in [
                    ("TELEGRAM_API_ID", self.TELEGRAM_API_ID),
                    ("TELEGRAM_CHANNEL_ID", self.TELEGRAM_CHANNEL_ID),
                ]
                if val == 0
            ]
            if empty:
                raise ValueError(f"Required in prod but missing/empty: {empty}")
        return self


settings = Settings()
