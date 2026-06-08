from app.news_parser.hashing import content_hash


def test_content_hash_is_sha256_hex():
    h = content_hash("Some Title", "https://example.com/a")
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_is_stable():
    assert content_hash("Title", "https://example.com/a") == content_hash(
        "Title", "https://example.com/a"
    )


def test_content_hash_normalizes_title_whitespace_and_case():
    assert content_hash("  Hello   World  ", "https://example.com/a") == content_hash(
        "hello world", "https://example.com/a"
    )


def test_content_hash_differs_on_url():
    assert content_hash("Title", "https://example.com/a") != content_hash(
        "Title", "https://example.com/b"
    )


def test_content_hash_differs_on_title():
    assert content_hash("Title A", "https://example.com/a") != content_hash(
        "Title B", "https://example.com/a"
    )


def test_content_hash_handles_none_url():
    h = content_hash("Title", None)
    assert isinstance(h, str)
    assert len(h) == 64
    # None and "" treated identically (both empty url component)
    assert content_hash("Title", None) == content_hash("Title", "")
