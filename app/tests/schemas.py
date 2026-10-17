import pytest
from pydantic import ValidationError

from app.schemas import Answer, Query


def test_query_strips_whitespace():
    query = Query(question="  find authentication  ")
    assert query.question == "find authentication"


def test_query_rejects_blank_question():
    with pytest.raises(ValidationError):
        Query(question="   ")


def test_query_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Query(question="test", unexpected="value")


def test_answer_rejects_duplicate_source_ids():
    with pytest.raises(ValidationError):
        Answer(
            answer="Found it",
            source_ids=["chunk-a", "chunk-a"],
            insufficient_context=False,
        )
