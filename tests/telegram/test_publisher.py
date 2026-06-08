from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram import publisher


def _fake_bot_cm(send_message_mock):
    """Build a Bot() return value that works as an async context manager."""
    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=False)
    bot.send_message = send_message_mock
    return bot


def test_publish_sends_and_returns_message_id():
    sent = MagicMock()
    sent.message_id = 4242
    send_message = AsyncMock(return_value=sent)
    bot = _fake_bot_cm(send_message)

    with patch.object(publisher, "Bot", return_value=bot) as bot_cls:
        result = publisher.publish(-1009999, "plain text")

    assert result == 4242
    # Bot constructed with the token (positional) inside the coroutine
    assert bot_cls.call_count == 1
    send_message.assert_awaited_once()
    kwargs = send_message.await_args.kwargs
    assert kwargs["chat_id"] == -1009999
    assert kwargs["text"] == "plain text"


def test_publish_sends_preformatted_html_verbatim():
    """text is already safe HTML (escaped body + <a> link) from format_post; the
    publisher must send it verbatim, NOT re-escape it (which would break the link)."""
    sent = MagicMock()
    sent.message_id = 1
    send_message = AsyncMock(return_value=sent)
    bot = _fake_bot_cm(send_message)

    html_msg = 'Ціна &lt; 1000$ 🎯\n\n🔗 <a href="https://e.com/a?x=1&amp;y=2">Читати джерело</a>'
    with patch.object(publisher, "Bot", return_value=bot):
        publisher.publish(-100, html_msg)

    kwargs = send_message.await_args.kwargs
    assert kwargs["text"] == html_msg  # verbatim, no double-escaping


def test_publish_propagates_send_errors():
    send_message = AsyncMock(side_effect=RuntimeError("boom"))
    bot = _fake_bot_cm(send_message)

    with patch.object(publisher, "Bot", return_value=bot):
        try:
            publisher.publish(-100123, "x")
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("expected RuntimeError to propagate")
