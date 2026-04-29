from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.music_agent.agent import MusicRecommenderAgent
from src.music_agent.config import get_settings
from src.music_agent.logging_utils import configure_logging


def evaluate_case(agent: MusicRecommenderAgent, case: dict) -> dict:
    style = case.get("style", "default")
    response = agent.recommend(case["query"], style=style)
    track_lookup = {t.id: t for t in agent.catalog.all_tracks}

    failures: list[str] = []

    if case.get("expect_refusal"):
        if not response.refused:
            failures.append("expected_refusal_but_got_recommendations")
        passed = len(failures) == 0
        return {
            "name": case["name"],
            "passed": passed,
            "failures": failures,
            "intent": response.intent,
            "confidence": response.confidence,
            "refused": response.refused,
        }

    if "expect_style_compliant" in case:
        if not response.style_metrics.get("compliant", False):
            failures.append(
                "style_violations: "
                + ", ".join(response.style_metrics.get("violations", ()))
            )

    if "expect_max_words" in case:
        words = response.style_metrics.get("word_count", 0)
        if words > case["expect_max_words"]:
            failures.append(f"summary_too_long: {words} > {case['expect_max_words']}")

    if "expect_baseline_word_delta_min" in case:
        baseline = agent.recommend(case["query"], style="default")
        delta = (baseline.style_metrics.get("word_count", 0) if baseline.style_metrics
                 else len(baseline.summary.split()))
        styled_words = (response.style_metrics.get("word_count", 0) if response.style_metrics
                        else len(response.summary.split()))
        observed = delta - styled_words
        if observed < case["expect_baseline_word_delta_min"]:
            failures.append(
                f"styled_not_shorter_enough: delta={observed} < "
                f"{case['expect_baseline_word_delta_min']}"
            )

    if "expect_intent" in case and response.intent != case["expect_intent"]:
        failures.append(f"intent_mismatch: got {response.intent} expected {case['expect_intent']}")

    if "expect_min_recommendations" in case:
        if len(response.recommendations) < case["expect_min_recommendations"]:
            failures.append(
                f"too_few_recommendations: got {len(response.recommendations)}"
            )

    if "expect_any_genre" in case:
        rec_genres = {r.genre for r in response.recommendations}
        if not (rec_genres & set(case["expect_any_genre"])):
            failures.append(f"no_expected_genre: got {sorted(rec_genres)}")

    if "expect_artist_in_results" in case:
        artists = {r.artist for r in response.recommendations}
        if case["expect_artist_in_results"] not in artists:
            failures.append(f"missing_artist: got {sorted(artists)}")

    if "expect_max_avg_energy" in case and response.recommendations:
        energies = [
            track_lookup[r.track_id].energy
            for r in response.recommendations
            if r.track_id in track_lookup
        ]
        avg = sum(energies) / max(1, len(energies))
        if avg > case["expect_max_avg_energy"]:
            failures.append(f"avg_energy_too_high: {avg:.2f}")

    if "expect_min_avg_energy" in case and response.recommendations:
        energies = [
            track_lookup[r.track_id].energy
            for r in response.recommendations
            if r.track_id in track_lookup
        ]
        avg = sum(energies) / max(1, len(energies))
        if avg < case["expect_min_avg_energy"]:
            failures.append(f"avg_energy_too_low: {avg:.2f}")

    passed = len(failures) == 0
    return {
        "name": case["name"],
        "passed": passed,
        "failures": failures,
        "intent": response.intent,
        "confidence": response.confidence,
        "style": response.style,
        "style_metrics": response.style_metrics,
        "recommendations": [
            {"title": r.title, "artist": r.artist, "genre": r.genre, "score": r.score}
            for r in response.recommendations
        ],
        "passed_checks": response.passed_checks,
        "checker_reasons": response.checker_reasons,
    }


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    agent = MusicRecommenderAgent(
        settings=settings,
        docs_path=Path("assets"),
        catalog_path=Path("data/tracks.json"),
    )
    cases = json.loads(Path("eval/cases.json").read_text(encoding="utf-8"))

    details = [evaluate_case(agent, case) for case in cases]
    total = len(details)
    passed = sum(1 for d in details if d["passed"])

    confidences = [d.get("confidence", 0) for d in details if "confidence" in d]
    avg_confidence = round(sum(confidences) / max(1, len(confidences)), 3)

    report = {
        "total": total,
        "passed": passed,
        "pass_rate_pct": round((passed / max(total, 1)) * 100, 2),
        "avg_confidence": avg_confidence,
        "details": details,
    }

    out_path = Path("eval/last_report.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
