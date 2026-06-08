from app.filter.language import detect_language


def test_detects_english():
    assert detect_language("The government announced a new election today.") == "en"


def test_detects_ukrainian():
    assert detect_language("Сьогодні уряд оголосив про нові вибори в країні.") == "uk"


def test_short_or_ambiguous_returns_none():
    # too little signal to be confident -> soft None
    assert detect_language("ok") is None


def test_disallowed_language_returns_none():
    # confident but not in ALLOWED_LANGUAGES (uk/ru/en) -> None
    out = detect_language("Das ist eine deutsche Nachricht über die Regierung heute.")
    assert out is None
