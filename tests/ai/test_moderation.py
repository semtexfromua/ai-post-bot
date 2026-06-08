import httpx
import respx

from app.ai.moderation import is_flagged


@respx.mock
def test_is_flagged_true_when_api_flags():
    respx.post("https://api.openai.com/v1/moderations").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "modr-1",
                "model": "omni-moderation-latest",
                "results": [{"flagged": True, "categories": {}, "category_scores": {}}],
            },
        )
    )
    assert is_flagged("щось погане") is True


@respx.mock
def test_is_flagged_false_when_clean():
    respx.post("https://api.openai.com/v1/moderations").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "modr-2",
                "model": "omni-moderation-latest",
                "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
            },
        )
    )
    assert is_flagged("звичайна новина про вибори") is False
