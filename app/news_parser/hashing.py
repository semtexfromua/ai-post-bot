from __future__ import annotations

import hashlib


def _normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def content_hash(title: str, url: str | None) -> str:
    """Stable sha256 dedup key over normalized title + url.

    Title is casefolded and whitespace-collapsed; url is taken verbatim
    (None treated as empty string). Components joined with a
    null-byte separator (vanishingly unlikely in real titles/URLs)
    to avoid title|url ambiguity.
    """
    norm_title = _normalize_title(title)
    norm_url = url or ""
    payload = f"{norm_title}\x00{norm_url}".encode()
    return hashlib.sha256(payload).hexdigest()
