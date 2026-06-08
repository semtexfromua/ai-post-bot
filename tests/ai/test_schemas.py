from app.ai.schemas import PostDraft


def test_postdraft_defaults_hashtags_to_empty_list():
    draft = PostDraft(text="Привіт світ", language="uk")
    assert draft.text == "Привіт світ"
    assert draft.language == "uk"
    assert draft.hashtags == []


def test_postdraft_accepts_hashtags():
    draft = PostDraft(text="t", language="en", hashtags=["#ai", "#news"])
    assert draft.hashtags == ["#ai", "#news"]
