import socket
import types
from unittest.mock import patch

import pytest

from app.news_parser import feed as feed_module
from app.news_parser import site as site_module
from app.news_parser.feed import FeedParser
from app.news_parser.site import SiteScraper
from app.news_parser.ssrf import (
    UnsafeURLError,
    assert_public_url,
    reject_literal_private_ip,
)


def _src(url, name="s"):
    return types.SimpleNamespace(
        url=url, name=name, etag=None, modified=None, last_seen_msg_id=None
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:6379",
        "http://localhost/admin",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    ],
)
def test_reject_literal_private_ip_blocks(url):
    with pytest.raises(UnsafeURLError):
        reject_literal_private_ip(url)


@pytest.mark.parametrize("url", ["https://dou.ua/rss", "http://8.8.8.8/x", "@channel"])
def test_reject_literal_private_ip_allows_public_and_domains(url):
    # domains aren't resolved here (DNS happens at fetch time); public literal IPs pass
    reject_literal_private_ip(url)  # must not raise


def test_assert_public_url_blocks_loopback_literal():
    # literal IP -> getaddrinfo returns it without network
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://127.0.0.1/x")


def test_assert_public_url_blocks_domain_resolving_to_private(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))],
    )
    with pytest.raises(UnsafeURLError):
        assert_public_url("https://evil.example.com/x")


def test_assert_public_url_allows_public(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )
    assert_public_url("https://example.com/x")  # must not raise


def test_site_scraper_blocks_internal_url_without_fetching():
    with patch.object(site_module.httpx, "get") as get:
        out = SiteScraper().fetch(_src("http://127.0.0.1:6379"))
    assert out == []
    get.assert_not_called()  # request never made


def test_feed_parser_blocks_internal_url_without_fetching():
    with patch.object(feed_module.feedparser, "parse") as parse:
        out = FeedParser().fetch(_src("http://169.254.169.254/feed"))
    assert out == []
    parse.assert_not_called()
