import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.keyword import Keyword


def test_create_keyword_row(db):
    kw = Keyword(word="нейромережа", lang="uk")
    db.add(kw)
    db.commit()
    db.refresh(kw)
    assert isinstance(kw.id, uuid.UUID)
    assert kw.word == "нейромережа"
    assert kw.lang == "uk"


def test_keyword_lang_optional(db):
    kw = Keyword(word="ai")
    db.add(kw)
    db.commit()
    db.refresh(kw)
    assert kw.lang is None


def test_keyword_word_unique_rejects_duplicate(db):
    db.add(Keyword(word="gpt"))
    db.commit()
    db.add(Keyword(word="gpt"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
