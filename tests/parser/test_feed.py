from datetime import UTC
from unittest.mock import MagicMock, patch

import feedparser

from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.feed import FeedParser

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example AI News</title>
    <item>
      <title>GPT released</title>
      <link>https://example.com/gpt</link>
      <description>A new model summary.</description>
      <pubDate>Mon, 08 Jun 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second story</title>
      <link>https://example.com/second</link>
      <description>Another summary.</description>
      <pubDate>Mon, 08 Jun 2026 11:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _make_source():
    src = MagicMock()
    src.type = SourceType.site
    src.url = "https://example.com/rss"
    src.name = "Example AI News"
    src.etag = None
    src.modified = None
    return src


def test_feed_parser_maps_fields_and_utc():
    parsed = feedparser.parse(SAMPLE_FEED)
    src = _make_source()
    with patch("app.news_parser.feed.feedparser.parse", return_value=parsed):
        items = FeedParser().fetch(src)

    assert len(items) == 2
    first = items[0]
    assert isinstance(first, NewsItemData)
    assert first.title == "GPT released"
    assert first.url == "https://example.com/gpt"
    assert first.summary == "A new model summary."
    assert first.source == "Example AI News"
    assert first.published_at.tzinfo == UTC
    assert first.published_at.hour == 10
    assert first.published_at.year == 2026


def test_feed_parser_passes_conditional_get_and_persists_validators():
    src = _make_source()
    src.etag = '"old-etag"'
    src.modified = "Mon, 01 Jun 2026 00:00:00 GMT"

    fake_parsed = feedparser.parse(SAMPLE_FEED)
    fake_parsed.etag = '"new-etag"'
    fake_parsed.modified = "Mon, 08 Jun 2026 10:00:00 GMT"

    with patch(
        "app.news_parser.feed.feedparser.parse", return_value=fake_parsed
    ) as mock_parse:
        FeedParser().fetch(src)

    # conditional GET validators forwarded
    _, kwargs = mock_parse.call_args
    assert kwargs.get("etag") == '"old-etag"'
    assert kwargs.get("modified") == "Mon, 01 Jun 2026 00:00:00 GMT"
    # new validators stored back on source
    assert src.etag == '"new-etag"'
    assert src.modified == "Mon, 08 Jun 2026 10:00:00 GMT"


def test_feed_parser_not_modified_returns_empty():
    src = _make_source()
    not_modified = feedparser.FeedParserDict()
    not_modified.status = 304
    not_modified.entries = []
    with patch("app.news_parser.feed.feedparser.parse", return_value=not_modified):
        items = FeedParser().fetch(src)
    assert items == []


def test_feed_parser_bozo_warns_but_still_parses():
    parsed = feedparser.parse(SAMPLE_FEED)
    parsed.bozo = 1
    parsed.bozo_exception = Exception("malformed")
    src = _make_source()
    with (
        patch("app.news_parser.feed.feedparser.parse", return_value=parsed),
        patch("app.news_parser.feed.logger.warning") as mock_warn,
    ):
        items = FeedParser().fetch(src)
    assert len(items) == 2
    assert mock_warn.called


def test_feed_parser_atom_uses_updated_when_no_published():
    """Atom entries commonly carry only <updated> (no <published>); use it as the
    publish date instead of stamping the parse moment."""
    atom = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Atom Example</title>
      <entry>
        <title>Atom story</title>
        <link href="https://example.com/atom"/>
        <summary>Atom summary.</summary>
        <updated>2026-06-01T18:30:02Z</updated>
      </entry>
    </feed>"""
    parsed = feedparser.parse(atom)
    src = _make_source()
    with patch("app.news_parser.feed.feedparser.parse", return_value=parsed):
        items = FeedParser().fetch(src)

    assert len(items) == 1
    pub = items[0].published_at
    assert pub.tzinfo == UTC
    assert (pub.year, pub.month, pub.day) == (2026, 6, 1)
    assert (pub.hour, pub.minute) == (18, 30)


def test_feed_parser_missing_pubdate_falls_back_to_now(monkeypatch):
    no_date_feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>X</title>
    <item><title>No date</title><link>https://example.com/x</link>
    <description>d</description></item></channel></rss>"""
    parsed = feedparser.parse(no_date_feed)
    src = _make_source()
    with patch("app.news_parser.feed.feedparser.parse", return_value=parsed):
        items = FeedParser().fetch(src)
    assert len(items) == 1
    assert items[0].published_at.tzinfo == UTC
