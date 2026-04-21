from __future__ import annotations

from src.faq_agent.cli import build_parser



def test_parser_accepts_question() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["What are your API limits?"])
    assert parsed.question == "What are your API limits?"
