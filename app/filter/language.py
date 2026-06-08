from lingua import LanguageDetectorBuilder

from app.core.config import settings

# Build a detector over ALL languages so we can recognise (and reject) a confident
# non-allowed language, but only accept results whose code is in ALLOWED_LANGUAGES.
_detector = (
    LanguageDetectorBuilder.from_all_languages()
    .with_preloaded_language_models()
    .build()
)

_ALLOWED = set(settings.ALLOWED_LANGUAGES)

# Minimum confidence to treat a detection as reliable ("soft": below this -> None).
_MIN_CONFIDENCE = 0.65


def language_verdict(text: str) -> str:
    """Run lingua once and return 'allowed', 'disallowed', or 'unknown'.

    - 'allowed'    – confident detection, language is in ALLOWED_LANGUAGES
    - 'disallowed' – confident detection, language is NOT in ALLOWED_LANGUAGES
    - 'unknown'    – empty text or confidence below _MIN_CONFIDENCE
    """
    if not text or not text.strip():
        return "unknown"
    values = _detector.compute_language_confidence_values(text)
    if not values:
        return "unknown"
    top = values[0]
    if top.value < _MIN_CONFIDENCE:
        return "unknown"
    # iso_code_639_1 is an IsoCode639_1 enum; .name is the 2-letter code.
    code = top.language.iso_code_639_1.name.lower()
    return "allowed" if code in _ALLOWED else "disallowed"
