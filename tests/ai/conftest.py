import pytest
from openai import OpenAI

from app.ai import generator, moderation


@pytest.fixture(autouse=True)
def _force_openai_endpoint(monkeypatch):
    """Pin the OpenAI client to the real api.openai.com endpoint for AI tests.

    The module-level clients are built at import time from settings.OPENAI_BASE_URL,
    so a developer .env pointing at OpenRouter would make respx (which mocks
    api.openai.com) miss. Rebinding both clients keeps these tests hermetic.
    """
    client = OpenAI(api_key="test", base_url="https://api.openai.com/v1")
    monkeypatch.setattr(generator, "_client", client)
    monkeypatch.setattr(moderation, "_client", client)
    # A developer .env may set MODERATION_ENABLED=false (OpenRouter has no
    # /moderations); force it on so moderation tests hit the mocked endpoint.
    monkeypatch.setattr(moderation.settings, "MODERATION_ENABLED", True)
