from __future__ import annotations

from pathlib import Path

from src.faq_agent.agent import AgenticFAQAssistant
from src.faq_agent.config import Settings



def _settings() -> Settings:
    return Settings(
        openai_api_key="",
        openai_model="gpt-4o-mini",
        log_level="INFO",
        top_k_retrieval=3,
        max_question_length=800,
    )



def test_answer_contains_citation() -> None:
    assistant = AgenticFAQAssistant(settings=_settings(), docs_path=Path("assets"))
    response = assistant.answer("What is the refund policy?")
    assert response.citations
    assert response.confidence > 0



def test_empty_question_raises() -> None:
    assistant = AgenticFAQAssistant(settings=_settings(), docs_path=Path("assets"))
    try:
        assistant.answer("   ")
        assert False, "Expected ValueError"
    except ValueError:
        assert True



def test_long_question_raises() -> None:
    assistant = AgenticFAQAssistant(settings=_settings(), docs_path=Path("assets"))
    long_question = "a" * 801
    try:
        assistant.answer(long_question)
        assert False, "Expected ValueError"
    except ValueError:
        assert True
