from app.filter.keywords import matches_keywords
from app.models.keyword import Keyword


def _kw(word: str, lang: str | None = None) -> Keyword:
    return Keyword(word=word, lang=lang)


def test_matches_inflected_form_via_lemma():
    # keyword "вибори" must match the inflected genitive "виборів"
    kws = [_kw("вибори")]
    assert (
        matches_keywords("сьогодні відбулося багато виборів у регіоні", kws, "any")
        is True
    )


def test_no_match_when_keyword_absent():
    kws = [_kw("економіка")]
    assert matches_keywords("сьогодні відбулося багато виборів", kws, "any") is False


def test_whole_word_only_no_substring_match():
    # "вибори" must NOT match inside an unrelated longer token
    kws = [_kw("вибори")]
    assert matches_keywords("розвиборимось колись", kws, "any") is False


def test_mode_all_requires_every_keyword():
    kws = [_kw("вибори"), _kw("президент")]
    text = "вибори президента відбулися"
    assert matches_keywords(text, kws, "all") is True
    assert matches_keywords("лише вибори без іншого", kws, "all") is False


def test_empty_keywords_returns_true():
    # no keywords configured -> nothing to filter on -> pass
    assert matches_keywords("будь-який текст", [], "any") is True


def test_lang_uk_matches_ukrainian_inflection():
    # "виборів" (genitive) lemmatizes to "вибори" under uk analyzer -> hit
    kws = [_kw("вибори", lang="uk")]
    assert matches_keywords("відбулося багато виборів у регіоні", kws, "any") is True


def test_lang_ru_does_not_match_ukrainian_inflection():
    # Same surface form "виборів" lemmatizes differently under ru analyzer
    # ("виборіть"), so the ru keyword "вибори" (→ "виборя") won't match.
    kws = [_kw("вибори", lang="ru")]
    assert matches_keywords("відбулося багато виборів у регіоні", kws, "any") is False
