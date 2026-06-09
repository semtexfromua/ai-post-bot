import html

from app.ai.schemas import PostDraft
from app.models.news_item import NewsItem

_MAX_HASHTAGS = 4


def _format_hashtags(tags: list[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        word = raw.strip().lstrip("#").replace(" ", "")
        if not word:
            continue
        tag = "#" + word
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
        if len(out) >= _MAX_HASHTAGS:
            break
    # Escape like the body/URL: hashtags come from the model and must not inject
    # markup into the HTML parse_mode payload the publisher sends.
    return " ".join(html.escape(tag) for tag in out)


def format_post(draft: PostDraft, news: NewsItem) -> str:
    """Build the final HTML message: escaped body + clickable source link + hashtags.

    parse_mode=HTML — only the interpolated fragments are escaped (so a source URL
    with '&' stays intact), therefore the publisher must NOT re-escape this string.
    """
    parts = [html.escape(draft.text.strip())]
    if news.url:
        href = html.escape(news.url, quote=True)
        parts.append(f'🔗 <a href="{href}">Читати джерело</a>')
    tags = _format_hashtags(draft.hashtags)
    if tags:
        parts.append(tags)
    return "\n\n".join(parts)
