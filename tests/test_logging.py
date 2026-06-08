import structlog

from app.core.logging import configure_logging


def test_configure_logging_binds_context():
    configure_logging()
    cap = structlog.testing.LogCapture()
    structlog.configure(processors=[cap])

    log = structlog.get_logger().bind(news_id="n-1")
    log.info("parsed")

    assert cap.entries[0]["event"] == "parsed"
    assert cap.entries[0]["news_id"] == "n-1"


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging()
    assert structlog.is_configured()
