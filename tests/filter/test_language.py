from app.filter.language import language_verdict


def test_allowed_english():
    assert (
        language_verdict("The government announced a new election today.") == "allowed"
    )


def test_allowed_ukrainian():
    assert (
        language_verdict("Сьогодні уряд оголосив про нові вибори в країні.")
        == "allowed"
    )


def test_uncertain_returns_unknown():
    # too little signal to be confident -> unknown
    assert language_verdict("ok") == "unknown"


def test_disallowed_language_returns_disallowed():
    # confident but not in ALLOWED_LANGUAGES -> disallowed
    result = language_verdict(
        "Das ist eine deutsche Nachricht über die Regierung heute."
    )
    assert result == "disallowed"
