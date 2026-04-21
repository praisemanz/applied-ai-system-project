from __future__ import annotations

import json
from pathlib import Path

from src.faq_agent.agent import AgenticFAQAssistant
from src.faq_agent.config import get_settings
from src.faq_agent.logging_utils import configure_logging



def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    assistant = AgenticFAQAssistant(settings=settings, docs_path=Path("assets"))
    cases = json.loads(Path("eval/cases.json").read_text(encoding="utf-8"))

    total = len(cases)
    passed = 0
    details = []

    for case in cases:
        response = assistant.answer(case["question"])
        answer_lower = response.answer.lower()

        include_hit = any(token.lower() in answer_lower for token in case["must_include_any"])
        citation_hit = bool(response.citations) if case.get("must_have_citation", False) else True
        check_hit = response.passed_checks
        case_pass = include_hit and citation_hit and check_hit

        if case_pass:
            passed += 1

        details.append(
            {
                "name": case["name"],
                "passed": case_pass,
                "include_hit": include_hit,
                "citation_hit": citation_hit,
                "check_hit": check_hit,
                "confidence": response.confidence,
                "citations": response.citations,
                "checker_reasons": response.checker_reasons,
            }
        )

    report = {
        "total": total,
        "passed": passed,
        "pass_rate": round((passed / max(total, 1)) * 100, 2),
        "details": details,
    }

    out_path = Path("eval/last_report.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
