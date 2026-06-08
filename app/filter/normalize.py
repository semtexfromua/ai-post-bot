import re
import unicodedata

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"\s+")

# Emoji / pictographic / symbol ranges to strip.
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # symbols, pictographs, emoji
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicators
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U00002190-\U000021ff"  # arrows
    "\U00002b00-\U00002bff"  # misc symbols and arrows
    "\U0000200d"             # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def normalize(text: str) -> str:
    """casefold + NFC + strip URLs/emoji + collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = _URL_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)
    text = text.casefold()
    text = _WS_RE.sub(" ", text)
    return text.strip()
