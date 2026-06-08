import os
from typing import Protocol

from openai import OpenAI

from app.ai.schemas import PostDraft
from app.core.config import settings
from app.models.news_item import NewsItem

_SYSTEM_PROMPT = (
    "Ти — редактор Telegram-каналу новин. На основі новини напиши лаконічний пост "
    "мовою джерела (uk/ru/en, тією ж, що й новина). Додай доречні емодзі та короткий "
    f"call-to-action. Довжина суворо не більше {settings.POST_MAX_LEN} символів. "
    "Поверни структуру: text (готовий пост), language (код мови), hashtags (список)."
)

# Module-level client (one per worker).
_client = OpenAI(
    api_key=settings.OPENAI_API_KEY.get_secret_value(),
    timeout=settings.OPENAI_TIMEOUT,
)


def _user_prompt(news: NewsItem) -> str:
    return (
        f"Заголовок: {news.title}\n"
        f"Опис: {news.summary or ''}\n"
        f"Текст: {news.raw_text or ''}\n"
        f"Джерело: {news.source}\n"
        f"URL: {news.url or ''}"
    )


class PostGenerator(Protocol):
    def generate(self, news: NewsItem) -> PostDraft: ...


class OpenAIGenerator:
    """Structured-output generator via openai chat.completions.parse."""

    def generate(self, news: NewsItem) -> PostDraft:
        completion = _client.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            temperature=0.75,
            max_completion_tokens=280,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(news)},
            ],
            response_format=PostDraft,
        )
        message = completion.choices[0].message
        if getattr(message, "refusal", None) or message.parsed is None:
            raise ValueError("OpenAI refused or returned no parsed output")
        return message.parsed


class FakeGenerator:
    """Deterministic generator for tests / offline mode (no network)."""

    def generate(self, news: NewsItem) -> PostDraft:
        return PostDraft(
            text=f"📰 {news.title}. Деталі за посиланням. Підписуйтесь!",
            language="uk",
            hashtags=[],
        )


def build_generator() -> PostGenerator:
    """Select generator: FakeGenerator when USE_FAKE_AI is set, else OpenAIGenerator."""
    if os.getenv("USE_FAKE_AI") == "1":
        return FakeGenerator()
    return OpenAIGenerator()
