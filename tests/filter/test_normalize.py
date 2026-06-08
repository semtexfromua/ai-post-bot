from app.filter.normalize import normalize


def test_normalize_casefolds_and_collapses_whitespace():
    assert normalize("  Вибори   В   Україні  ") == "вибори в україні"


def test_normalize_strips_urls():
    out = normalize("Новина тут https://example.com/path?x=1 кінець")
    assert "http" not in out
    assert "вибори" not in out  # sanity
    assert out == "новина тут кінець"


def test_normalize_strips_emoji():
    assert normalize("Перемога 🎉🔥 сьогодні") == "перемога сьогодні"


def test_normalize_nfc_composes_combining_marks():
    # "й" as base "и" + combining breve U+0306 must normalise to single NFC codepoint
    decomposed = "й"
    composed = "й"
    assert normalize(decomposed) == normalize(composed)
