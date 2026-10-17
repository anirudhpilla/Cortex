import pytest

from app.agent import validate_answer
from app.schemas import Answer

def test_valid_answer():
    answer = Answer(
        answer="The function validates access tokens.",
        source_ids=["chunk-a"],
        insufficient_context=False,
    )

    result = validate_answer(answer, {"chunk-a", "chunk-b"})
    assert result.source_ids == ["chunk-a"]

def test_rejects_unknown_source_id():
    answer = Answer(
        answer="Found it.",
        source_ids=["unknown"],
        insufficient_context=False,
    )

    with pytest.raises(ValueError):
        validate_answer(answer, {"chunk-a"})

def test_rejects_citations_when_context_is_insufficient():
    answer = Answer(
        answer="Not enough evidence.",
        source_ids=["chunk-a"],
        insufficient_context=True,
    )

    with pytest.raises(ValueError):
        validate_answer(answer, {"chunk-a"})

def test_rejects_uncited_supported_answer():
    answer = Answer(
        answer="The function does something.",
        source_ids=[],
        insufficient_context=False,
    )

    with pytest.raises(ValueError):
        validate_answer(answer, {"chunk-a"})
