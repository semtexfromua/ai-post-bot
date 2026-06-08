from app.filter.dedup import is_duplicate
from app.filter.keywords import matches_keywords
from app.filter.language import _MIN_CONFIDENCE, _detector
from app.filter.normalize import normalize
from app.models.keyword import Keyword
from app.models.news_item import NewsItem


def _searchable_text(item: NewsItem) -> str:
    parts = [item.title, item.summary or "", item.raw_text or ""]
    return " ".join(p for p in parts if p)


def _is_confidently_disallowed(text: str, settings) -> bool:
    """True when lingua is confident the text is a non-allowed language."""
    if not text or not text.strip():
        return False
    values = _detector.compute_language_confidence_values(text)
    if not values:
        return False
    top = values[0]
    if top.value < _MIN_CONFIDENCE:
        return False
    code = top.language.iso_code_639_1.name.lower()
    return code not in set(settings.ALLOWED_LANGUAGES)


def passes_filters(item: NewsItem, keywords: list[Keyword], redis_client, settings) -> bool:
    """Filter gate. Order: dedup -> language (soft) -> keywords.

    Returns True if the item should continue down the pipeline.
    """
    # 1) dedup (records the hash atomically; True means already seen)
    if is_duplicate(item.content_hash, redis_client):
        return False

    raw_text = _searchable_text(item)
    text = normalize(raw_text)

    # 2) language: soft signal. Drop only on a confident DISALLOWED language.
    lang = detect_language_code(raw_text)
    # detect_language returns a code only when it is an allowed language;
    # to distinguish "confident-but-disallowed" from "uncertain" we re-check raw.
    if lang is None and _is_confidently_disallowed(raw_text, settings):
        return False

    # 3) keywords (whole-word lemma match)
    return matches_keywords(text, keywords, settings.KEYWORD_MATCH_MODE)


def detect_language_code(text: str) -> str | None:
    """Thin wrapper around _detector for internal use."""
    from app.filter.language import detect_language

    return detect_language(text)
