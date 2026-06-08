import os

from openai import OpenAI

from app.core.config import settings

_MODERATION_MODEL = "omni-moderation-latest"

# Module-level client (one per worker).
_client = OpenAI(
    api_key=settings.OPENAI_API_KEY.get_secret_value(),
    base_url=settings.OPENAI_BASE_URL,
    timeout=settings.OPENAI_TIMEOUT,
)


def is_flagged(text: str) -> bool:
    """Return True if the moderation endpoint flags the text.

    Skipped in fake mode and when MODERATION_ENABLED is off (OpenAI-compatible
    providers such as OpenRouter have no /moderations endpoint).
    """
    if os.getenv("USE_FAKE_AI") == "1" or not settings.MODERATION_ENABLED:
        return False
    resp = _client.moderations.create(model=_MODERATION_MODEL, input=text)
    return bool(resp.results[0].flagged)
