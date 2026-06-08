from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["local", "prod"] = "local"

    DATABASE_URL: str = "sqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 30

    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: SecretStr = SecretStr("")
    TELETHON_STRING_SESSION: SecretStr = SecretStr("")
    TELEGRAM_BOT_TOKEN: SecretStr = SecretStr("")
    TELEGRAM_CHANNEL_ID: int = 0

    ALLOWED_LANGUAGES: list[str] = ["uk", "ru", "en"]
    DEDUP_TTL_SECONDS: int = 604800
    KEYWORD_MATCH_MODE: Literal["any", "all"] = "any"
    POST_MAX_LEN: int = 4096


settings = Settings()
