from __future__ import annotations

from pathlib import Path

from src.music_agent.track_catalog import TrackCatalog, TrackQuery


CATALOG_PATH = Path("data/tracks.json")


def test_catalog_loads_all_tracks() -> None:
    catalog = TrackCatalog.from_json(CATALOG_PATH)
    assert len(catalog.all_tracks) >= 20
    # Required fields populated.
    sample = catalog.all_tracks[0]
    assert sample.id and sample.title and sample.artist
    assert 0.0 <= sample.energy <= 1.0
    assert 0.0 <= sample.valence <= 1.0


def test_genre_filter_excludes_other_genres() -> None:
    catalog = TrackCatalog.from_json(CATALOG_PATH)
    results = catalog.search(TrackQuery(genres=("Lo-fi Hip Hop",)), top_k=10)
    assert results, "expected lo-fi tracks in catalog"
    for r in results:
        assert r.track.genre == "Lo-fi Hip Hop"


def test_mood_filter_returns_focus_tracks() -> None:
    catalog = TrackCatalog.from_json(CATALOG_PATH)
    results = catalog.search(
        TrackQuery(moods=("focus",), target_energy=0.3, target_valence=0.5),
        top_k=5,
    )
    assert results, "expected focus tracks"
    # At least one returned track lists 'focus' as a mood.
    assert any("focus" in {m.lower() for m in r.track.moods} for r in results)


def test_unmatchable_query_returns_empty() -> None:
    catalog = TrackCatalog.from_json(CATALOG_PATH)
    results = catalog.search(TrackQuery(genres=("Nonexistent Genre",)), top_k=5)
    assert results == []
