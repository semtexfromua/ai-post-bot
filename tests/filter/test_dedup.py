import fakeredis

from app.filter.dedup import is_duplicate


def test_first_seen_is_not_duplicate_then_subsequent_is():
    r = fakeredis.FakeStrictRedis()
    h = "abc123hash"
    assert is_duplicate(h, r) is False  # first time -> stored, not a dup
    assert is_duplicate(h, r) is True   # second time -> already seen -> dup


def test_distinct_hashes_independent():
    r = fakeredis.FakeStrictRedis()
    assert is_duplicate("hash-a", r) is False
    assert is_duplicate("hash-b", r) is False


def test_key_has_ttl_set():
    r = fakeredis.FakeStrictRedis()
    is_duplicate("ttl-hash", r)
    assert r.ttl("m4:seen:ttl-hash") > 0
