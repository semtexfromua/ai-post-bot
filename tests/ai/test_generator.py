import json
from datetime import UTC, datetime

import httpx
import respx

from app.ai.generator import FakeGenerator, OpenAIGenerator, build_generator
from app.ai.schemas import PostDraft
from app.models.news_item import NewsItem


def _news() -> NewsItem:
    return NewsItem(
        title="Уряд оголосив нові вибори",
        url="https://example.com/a",
        summary="Деталі про дату та умови проведення виборів.",
        source="Example",
        published_at=datetime.now(UTC),
        raw_text="Повний текст новини про вибори.",
        content_hash="hash-gen-1",
    )


def test_fake_generator_returns_postdraft():
    draft = FakeGenerator().generate(_news())
    assert isinstance(draft, PostDraft)
    assert draft.text
    assert draft.language


@respx.mock
def test_openai_generator_parses_structured_output():
    parsed = PostDraft(
        text="🗳️ Уряд оголосив нові вибори! Стежте за оновленнями.",
        language="uk",
        hashtags=["#вибори"],
    )
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": parsed.model_dump_json(),
                            "refusal": None,
                            "parsed": json.loads(parsed.model_dump_json()),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )
    )
    draft = OpenAIGenerator().generate(_news())
    assert isinstance(draft, PostDraft)
    assert draft.language == "uk"
    assert "вибори" in draft.text.casefold()


@respx.mock
def test_openai_generator_length_finish_raises_clean_valueerror():
    """A completion truncated by the token cap (finish_reason='length') must
    surface as a clean ValueError, not an opaque SDK LengthFinishReasonError."""
    import pytest

    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-2",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length",
                        "message": {
                            "role": "assistant",
                            "content": "truncated...",
                            "refusal": None,
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )
    )
    with pytest.raises(ValueError):
        OpenAIGenerator().generate(_news())


def test_build_generator_returns_fake_when_flagged(monkeypatch):
    monkeypatch.setenv("USE_FAKE_AI", "1")
    gen = build_generator()
    assert isinstance(gen, FakeGenerator)
