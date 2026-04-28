from __future__ import annotations

from pathlib import Path

from src.music_agent.planner import build_plan
from src.music_agent.track_catalog import TrackCatalog


CATALOG = TrackCatalog.from_json(Path("data/tracks.json"))


def test_focus_query_detects_focus_mood_and_low_energy_target() -> None:
    plan = build_plan("Need calm music for studying", CATALOG)
    assert "focus" in plan.moods or "calm" in plan.moods
    assert plan.target_energy is not None and plan.target_energy < 0.5
    assert plan.intent in {"mood", "genre_and_mood", "open_ended"}


def test_artist_query_detects_artist_intent() -> None:
    plan = build_plan("Recommend music similar to Daft Punk", CATALOG)
    assert "Daft Punk" in plan.artists
    assert plan.intent == "similar_artist"


def test_genre_query_detects_genre() -> None:
    plan = build_plan("Some Lo-fi Hip Hop please", CATALOG)
    assert "Lo-fi Hip Hop" in plan.genres


def test_workout_query_targets_high_energy() -> None:
    plan = build_plan("intense workout playlist for the gym", CATALOG)
    assert "energetic" in plan.moods
    assert plan.target_energy is not None and plan.target_energy > 0.7
