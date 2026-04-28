from __future__ import annotations

from src.music_agent.cli import build_parser


def test_parser_accepts_query() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["chill study music"])
    assert parsed.query == "chill study music"
    assert parsed.docs_path == "assets"
    assert parsed.catalog_path == "data/tracks.json"
