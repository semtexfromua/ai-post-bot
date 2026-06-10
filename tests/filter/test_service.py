import datetime

from app.core.config import settings
from app.filter.service import passes_filters
from app.models.keyword import Keyword
from app.models.news_item import NewsItem


def _news(title: str, summary: str | None = None) -> NewsItem:
    return NewsItem(
        title=title,
        url="https://example.com/a",
        summary=summary,
        source="Example",
        published_at=datetime.datetime.now(datetime.UTC),
        raw_text=summary or title,
        content_hash="hash-" + title[:8],
    )


def _kw(word: str) -> Keyword:
    return Keyword(word=word)


def test_passes_when_allowed_lang_and_keyword_hits_inflected():
    item = _news("Сьогодні відбулося багато виборів у країні")
    assert passes_filters(item, [_kw("вибори")], settings) is True


def test_dropped_when_keyword_absent():
    item = _news("Сьогодні гарна погода в місті")
    assert passes_filters(item, [_kw("вибори")], settings) is False


def test_dropped_on_confident_disallowed_language():
    item = _news(
        "Das ist eine lange deutsche Nachricht über die Regierung heute Abend."
    )
    assert passes_filters(item, [], settings) is False


def test_dropped_when_source_disabled():
    # source filter gates before keywords: a keyword match must not save a disabled source
    item = _news("Сьогодні відбулося багато виборів у країні")
    assert (
        passes_filters(item, [_kw("вибори")], settings, source_enabled=False) is False
    )
