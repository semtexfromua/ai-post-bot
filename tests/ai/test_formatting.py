from datetime import UTC, datetime

from app.ai.formatting import format_post
from app.ai.schemas import PostDraft
from app.models.news_item import NewsItem


def _news(url="https://example.com/a?x=1&y=2"):
    return NewsItem(
        title="t",
        url=url,
        summary="s",
        source="Example",
        published_at=datetime.now(UTC),
        raw_text="r",
        content_hash="h",
    )


def test_format_post_escapes_body_and_appends_link_and_tags():
    draft = PostDraft(
        text="Ціна < 1000$ & більше 🎯", language="uk", hashtags=["Python", "ai"]
    )
    out = format_post(draft, _news())
    # body escaped
    assert "Ціна &lt; 1000$ &amp; більше 🎯" in out
    # clickable source link with the URL intact (NOT escaped to break &)
    assert '<a href="https://example.com/a?x=1&amp;y=2">Читати джерело</a>' in out
    # hashtags normalized with leading #
    assert out.strip().endswith("#Python #ai")


def test_format_post_without_url_has_no_link():
    draft = PostDraft(text="Текст без лінка", language="uk", hashtags=[])
    out = format_post(draft, _news(url=None))
    assert "<a href" not in out
    assert out == "Текст без лінка"


def test_format_post_normalizes_hashtags():
    draft = PostDraft(
        text="x", language="uk", hashtags=["#Python", "machine learning", "", "Python"]
    )
    out = format_post(draft, _news(url=None))
    # leading # added, spaces removed, dedup case-insensitive, capped
    assert "#Python" in out
    assert "#machinelearning" in out
    assert out.count("#Python") == 1
