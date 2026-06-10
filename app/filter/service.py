from app.filter.keywords import matches_keywords
from app.filter.language import language_verdict
from app.filter.normalize import normalize
from app.models.keyword import Keyword
from app.models.news_item import NewsItem


def _searchable_text(item: NewsItem) -> str:
    parts = [item.title, item.summary or "", item.raw_text or ""]
    return " ".join(p for p in parts if p)


def passes_filters(
    item: NewsItem,
    keywords: list[Keyword],
    settings,
    *,
    source_enabled: bool = True,
) -> bool:
    """Filter gate. Order: source -> language (soft) -> keywords.

    Returns True if the item should continue down the pipeline. Deduplication is
    handled durably upstream by the content_hash UNIQUE constraint in parse_source,
    so the gate is replay-safe: a redelivered item (acks_late) is never dropped
    here. `source_enabled` is False when the item's originating Source is currently
    disabled (the caller resolves it).
    """
    # 0) source: drop items whose originating source is currently disabled.
    if not source_enabled:
        return False

    raw_text = _searchable_text(item)
    text = normalize(raw_text)

    # 1) language: soft signal. Drop only on a confident DISALLOWED language.
    if language_verdict(raw_text) == "disallowed":
        return False

    # 2) keywords (whole-word lemma match)
    return matches_keywords(text, keywords, settings.KEYWORD_MATCH_MODE)
