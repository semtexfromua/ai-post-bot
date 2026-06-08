from unittest.mock import patch

from app.tasks import pipeline


def test_generate_post_skips_on_none():
    # generate_post must not touch the DB or generator when fed None
    with patch.object(pipeline, "SessionLocal") as sl:
        result = pipeline.generate_post.run(None)
    assert result is None
    sl.assert_not_called()


def test_chain_dies_when_filter_returns_none():
    # simulate the chain hand-off: filter -> None -> generate -> None -> publish
    gen_out = pipeline.generate_post.run(None)
    assert gen_out is None
    with patch.object(pipeline.publisher, "publish") as pub:
        pub_out = pipeline.publish_post.run(gen_out)
    assert pub_out is None
    pub.assert_not_called()
