from __future__ import annotations

import argparse
import json
from pathlib import Path

from tabulate import tabulate

from .agent import MusicRecommenderAgent
from .config import get_settings
from .logging_utils import configure_logging, log_trace
from .profiles import load_profiles
from .scoring import ALL_MODES, ScoredSong, recommend_songs
from .specialization import (
    ALL_STYLES,
    render_styled_fallback,
    style_compliance,
)
from .track_catalog import RankedTrack, TrackCatalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic music recommender with RAG")
    parser.add_argument(
        "query",
        type=str,
        nargs="?",
        default=None,
        help="Free-form mood/genre/artist query (omit when using --profile)",
    )
    parser.add_argument("--profile", type=str, help="Profile key from data/profiles.json")
    parser.add_argument(
        "--mode",
        type=str,
        default="mood_first",
        choices=list(ALL_MODES),
        help="Ranking mode (mood_first | genre_first | energy_similarity)",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of recommendations to return"
    )
    parser.add_argument(
        "--artist-penalty",
        type=float,
        default=0.5,
        help="Diversity penalty applied to repeat artists (0 disables)",
    )
    parser.add_argument(
        "--docs-path", type=str, default="assets",
        help="Directory containing markdown knowledge files",
    )
    parser.add_argument(
        "--catalog-path", type=str, default="data/tracks.json",
        help="Path to the structured track catalog JSON",
    )
    parser.add_argument(
        "--profiles-path", type=str, default="data/profiles.json",
        help="Path to the user profiles JSON",
    )
    parser.add_argument(
        "--style",
        type=str,
        default="default",
        choices=list(ALL_STYLES),
        help="Summary style: default | dj_brief | studio_notes (specialization stretch)",
    )
    parser.add_argument("--table", action="store_true", help="Render results as a table")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.profile and not args.query:
        parser.error("provide a free-form QUERY or --profile <key>")

    settings = get_settings()
    configure_logging(settings.log_level)

    if args.profile:
        run_profile_mode(args, settings)
    else:
        run_query_mode(args, settings)


def run_profile_mode(args: argparse.Namespace, settings) -> None:
    profiles = load_profiles(Path(args.profiles_path))
    if args.profile not in profiles:
        raise SystemExit(
            f"Unknown profile '{args.profile}'. Available: {', '.join(sorted(profiles))}"
        )
    prefs = profiles[args.profile]

    catalog = TrackCatalog.from_json(Path(args.catalog_path))
    scored = recommend_songs(
        prefs=prefs,
        songs=catalog.all_tracks,
        top_k=args.top_k,
        mode=args.mode,
        artist_penalty=args.artist_penalty,
    )

    styled_summary = _styled_profile_summary(scored, prefs, args.style)
    style_metrics = (
        style_compliance(styled_summary, args.style)
        if args.style != "default" and scored
        else {}
    )

    log_trace(
        "profile_recommend",
        {
            "profile": prefs.name,
            "mode": args.mode,
            "style": args.style,
            "style_metrics": style_metrics,
            "artist_penalty": args.artist_penalty,
            "track_ids": [s.track.id for s in scored],
        },
    )

    if args.json:
        payload = {
            "profile": prefs.name,
            "style": args.style,
            "style_metrics": style_metrics,
            "summary": styled_summary,
            "tracks": _scored_to_dicts(scored),
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"Profile: {prefs.name}")
    print(f"Description: {prefs.description}")
    print(f"Ranking mode: {args.mode}    |    Style: {args.style}")
    print(f"Artist penalty: {args.artist_penalty}\n")

    if args.table:
        print(_render_table(scored))
    else:
        _render_list(scored)

    if args.style != "default" and scored:
        print("\nStyled summary:")
        print(styled_summary)
        m = style_metrics
        print(
            f"\nStyle metrics: words={m.get('word_count')}, "
            f"second_person={m.get('has_second_person')}, "
            f"bullets={m.get('has_bullets')}, "
            f"compliant={m.get('compliant')}"
        )


def _styled_profile_summary(scored: list[ScoredSong], prefs, style: str) -> str:
    if not scored or style == "default":
        return ""
    from .planner import Plan
    plan = Plan(
        intent="profile",
        moods=tuple(prefs.favorite_moods),
        genres=tuple(prefs.favorite_genres),
        artists=tuple(prefs.favorite_artists),
        eras=(),
        tempo_range=prefs.tempo_range,
        target_energy=prefs.target_energy,
        target_valence=prefs.target_valence,
        target_acousticness=prefs.target_acousticness,
        success_criteria=(),
        raw_query=prefs.description,
    )
    ranked = [
        RankedTrack(track=s.track, score=s.score, reasons=s.reasons) for s in scored
    ]
    return render_styled_fallback(style, plan, [], ranked)


def run_query_mode(args: argparse.Namespace, settings) -> None:
    agent = MusicRecommenderAgent(
        settings=settings,
        docs_path=Path(args.docs_path),
        catalog_path=Path(args.catalog_path),
    )
    response = agent.recommend(
        args.query,
        mode=args.mode,
        artist_penalty=args.artist_penalty,
        style=args.style,
    )

    log_trace(
        "final_response",
        {
            "query": args.query,
            "intent": response.intent,
            "mode": args.mode,
            "style": response.style,
            "style_metrics": response.style_metrics,
            "confidence": response.confidence,
            "passed_checks": response.passed_checks,
            "track_ids": [r.track_id for r in response.recommendations],
            "citations": response.citations,
        },
    )

    if args.json:
        print(
            json.dumps(
                {
                    "summary": response.summary,
                    "intent": response.intent,
                    "mode": args.mode,
                    "style": response.style,
                    "style_metrics": response.style_metrics,
                    "recommendations": [r.__dict__ for r in response.recommendations],
                    "citations": response.citations,
                    "confidence": response.confidence,
                    "passed_checks": response.passed_checks,
                    "checker_reasons": response.checker_reasons,
                    "refused": response.refused,
                },
                indent=2,
            )
        )
        return

    print(f"Intent: {response.intent}    |    Mode: {args.mode}    |    Style: {response.style}")
    if args.table and response.recommendations:
        rows = [
            [r.title, r.artist, r.genre, r.score, r.why]
            for r in response.recommendations
        ]
        print()
        print(tabulate(
            rows,
            headers=["Title", "Artist", "Genre", "Score", "Why"],
            tablefmt="github",
            maxcolwidths=[None, None, None, None, 60],
        ))
    else:
        print("\nRecommendations:")
        if not response.recommendations:
            print("  (none — try a broader mood, genre, or artist)")
        for rec in response.recommendations:
            print(f"  - {rec.title} by {rec.artist}  [{rec.genre}]  score={rec.score}")
            print(f"      why: {rec.why}")

    print("\nSummary:")
    print(response.summary)

    print("\nCitations:")
    for citation in response.citations:
        print(f"  - {citation}")

    print(f"\nConfidence: {response.confidence}")
    print(f"Checks passed: {response.passed_checks}")
    if response.checker_reasons:
        print(f"Checker notes: {', '.join(response.checker_reasons)}")
    if response.style != "default" and response.style_metrics:
        m = response.style_metrics
        print(
            f"Style metrics: words={m.get('word_count')}, "
            f"second_person={m.get('has_second_person')}, "
            f"bullets={m.get('has_bullets')}, "
            f"compliant={m.get('compliant')}"
        )


def _render_table(scored: list[ScoredSong]) -> str:
    rows = [
        [
            i + 1,
            s.track.title,
            s.track.artist,
            s.track.genre,
            s.track.tempo_bpm,
            s.track.energy,
            s.score,
            "; ".join(s.reasons),
        ]
        for i, s in enumerate(scored)
    ]
    return tabulate(
        rows,
        headers=["#", "Title", "Artist", "Genre", "BPM", "Energy", "Score", "Why"],
        tablefmt="github",
        maxcolwidths=[None, None, None, None, None, None, None, 50],
    )


def _render_list(scored: list[ScoredSong]) -> None:
    print("Recommendations:")
    if not scored:
        print("  (no matches — try a different profile or mode)")
    for i, s in enumerate(scored, start=1):
        t = s.track
        print(f"  {i}. {t.title} by {t.artist}  [{t.genre}]  score={s.score}")
        print(
            f"     features: tempo={t.tempo_bpm} BPM, energy={t.energy}, "
            f"valence={t.valence}, danceability={t.danceability}, popularity={t.popularity}"
        )
        print(f"     why: {'; '.join(s.reasons) or 'matches profile'}")


def _scored_to_dicts(scored: list[ScoredSong]) -> list[dict]:
    return [
        {
            "id": s.track.id,
            "title": s.track.title,
            "artist": s.track.artist,
            "genre": s.track.genre,
            "tempo_bpm": s.track.tempo_bpm,
            "energy": s.track.energy,
            "valence": s.track.valence,
            "danceability": s.track.danceability,
            "popularity": s.track.popularity,
            "score": s.score,
            "reasons": list(s.reasons),
        }
        for s in scored
    ]


if __name__ == "__main__":
    main()
