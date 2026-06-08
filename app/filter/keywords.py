import re

import pymorphy3

from app.models.keyword import Keyword

# Module-level singletons (init once per worker).
_morph_uk = pymorphy3.MorphAnalyzer(lang="uk")
_morph_ru = pymorphy3.MorphAnalyzer(lang="ru")

# Token = run of word characters (letters/digits/underscore), Unicode-aware.
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _lemmatize_with(morph: pymorphy3.MorphAnalyzer, token: str) -> set[str]:
    """Lemmas for a single token via one analyzer (includes the token itself)."""
    lemmas: set[str] = {token}
    parsed = morph.parse(token)
    if parsed:
        lemmas.add(parsed[0].normal_form)
    return lemmas


def _text_lemmas_lang(text: str, morph: pymorphy3.MorphAnalyzer) -> set[str]:
    """Lemma set for text using a single language analyzer."""
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(text.casefold()):
        out |= _lemmatize_with(morph, tok)
    return out


def _keyword_lemma(word: str, lang: str | None) -> str:
    """Normal form of the first token in *word* using the appropriate analyzer."""
    tokens = _TOKEN_RE.findall(word.casefold())
    if not tokens:
        return word.casefold()
    first = tokens[0]
    morph = _morph_ru if lang == "ru" else _morph_uk
    parsed = morph.parse(first)
    if parsed:
        return parsed[0].normal_form
    return first


def matches_keywords(text: str, keywords: list[Keyword], mode: str) -> bool:
    """Whole-word, lemma-based keyword match respecting keyword.lang.

    - lang="uk"  → match against Ukrainian lemmas only
    - lang="ru"  → match against Russian lemmas only
    - lang=None or lang="en" → match against the union (uk ∪ ru)

    mode "any" -> at least one keyword present; "all" -> every keyword present.
    Empty keyword list -> True (nothing to filter on).
    """
    if not keywords:
        return True

    # Lemmatize text once per language; build union lazily.
    _uk: set[str] | None = None
    _ru: set[str] | None = None
    _union: set[str] | None = None

    def uk() -> set[str]:
        nonlocal _uk
        if _uk is None:
            _uk = _text_lemmas_lang(text, _morph_uk)
        return _uk

    def ru() -> set[str]:
        nonlocal _ru
        if _ru is None:
            _ru = _text_lemmas_lang(text, _morph_ru)
        return _ru

    def union() -> set[str]:
        nonlocal _union
        if _union is None:
            _union = uk() | ru()
        return _union

    def _hit(kw: Keyword) -> bool:
        lemma = _keyword_lemma(kw.word, kw.lang)
        if kw.lang == "uk":
            return lemma in uk()
        if kw.lang == "ru":
            return lemma in ru()
        return lemma in union()

    results = [_hit(kw) for kw in keywords]
    if mode == "all":
        return all(results)
    return any(results)
