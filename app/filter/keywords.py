import re

import pymorphy3

from app.models.keyword import Keyword

# Module-level singletons (init once per worker).
_morph_uk = pymorphy3.MorphAnalyzer(lang="uk")
_morph_ru = pymorphy3.MorphAnalyzer(lang="ru")

# Token = run of word characters (letters/digits/underscore), Unicode-aware.
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _lemmatize(token: str) -> set[str]:
    """All normal forms (lemmas) of a token across uk and ru analyzers."""
    lemmas: set[str] = {token}
    for morph in (_morph_uk, _morph_ru):
        parsed = morph.parse(token)
        if parsed:
            lemmas.add(parsed[0].normal_form)
    return lemmas


def _text_lemmas(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(text.casefold()):
        out |= _lemmatize(tok)
    return out


def _keyword_lemma(word: str) -> str:
    tokens = _TOKEN_RE.findall(word.casefold())
    if not tokens:
        return word.casefold()
    first = tokens[0]
    parsed = _morph_uk.parse(first)
    if parsed:
        return parsed[0].normal_form
    parsed_ru = _morph_ru.parse(first)
    if parsed_ru:
        return parsed_ru[0].normal_form
    return first


def matches_keywords(text: str, keywords: list[Keyword], mode: str) -> bool:
    """Whole-word, lemma-based keyword match.

    mode "any" -> at least one keyword present; "all" -> every keyword present.
    Empty keyword list -> True (nothing to filter on).
    """
    if not keywords:
        return True
    haystack = _text_lemmas(text)
    results = [_keyword_lemma(kw.word) in haystack for kw in keywords]
    if mode == "all":
        return all(results)
    return any(results)
