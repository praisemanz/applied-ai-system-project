from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import AgenticFAQAssistant
from .config import get_settings
from .logging_utils import configure_logging, log_trace



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic FAQ assistant")
    parser.add_argument("question", type=str, help="Question to ask")
    parser.add_argument(
        "--docs-path",
        type=str,
        default="assets",
        help="Directory containing markdown knowledge files",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    assistant = AgenticFAQAssistant(settings=settings, docs_path=Path(args.docs_path))
    response = assistant.answer(args.question)

    log_trace(
        "final_response",
        {
            "question": args.question,
            "confidence": response.confidence,
            "passed_checks": response.passed_checks,
            "citations": response.citations,
        },
    )

    if args.json:
        print(
            json.dumps(
                {
                    "answer": response.answer,
                    "confidence": response.confidence,
                    "citations": response.citations,
                    "passed_checks": response.passed_checks,
                    "checker_reasons": response.checker_reasons,
                },
                indent=2,
            )
        )
        return

    print("Answer:")
    print(response.answer)
    print("\nCitations:")
    for citation in response.citations:
        print(f"- {citation}")
    print(f"\nConfidence: {response.confidence}")
    print(f"Checks passed: {response.passed_checks}")
    if response.checker_reasons:
        print(f"Checker notes: {', '.join(response.checker_reasons)}")


if __name__ == "__main__":
    main()
