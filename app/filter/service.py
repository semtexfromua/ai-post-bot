from app.filter.dedup import is_duplicate
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
    redis_client,
    settings,
    *,
    source_enabled: bool = True,
) -> bool:
    """Filter gate. Order: source -> dedup -> language (soft) -> keywords.

    Returns True if the item should continue down the pipeline.
    `source_enabled` is False when the item's originating Source is currently
    disabled (the caller resolves it); checked first so a disabled source is
    dropped without consuming a dedup slot.
    """
    # 0) source: drop items whose originating source is currently disabled.
    if not source_enabled:
        return False

    # 1) dedup (records the hash atomically; True means already seen)
    if is_duplicate(item.content_hash, redis_client):
        return False

    raw_text = _searchable_text(item)
    text = normalize(raw_text)

    # 2) language: soft signal. Drop only on a confident DISALLOWED language.
    if language_verdict(raw_text) == "disallowed":
        return False

    # 3) keywords (whole-word lemma match)
    return matches_keywords(text, keywords, settings.KEYWORD_MATCH_MODE)
