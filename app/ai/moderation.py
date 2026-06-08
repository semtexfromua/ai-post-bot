from openai import OpenAI

from app.core.config import settings

_MODERATION_MODEL = "omni-moderation-latest"

# Module-level client (one per worker).
_client = OpenAI(
    api_key=settings.OPENAI_API_KEY.get_secret_value(),
    timeout=settings.OPENAI_TIMEOUT,
)


def is_flagged(text: str) -> bool:
    """Return True if the moderation endpoint flags the text."""
    resp = _client.moderations.create(model=_MODERATION_MODEL, input=text)
    return bool(resp.results[0].flagged)
