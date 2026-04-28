from __future__ import annotations

from pathlib import Path

import pytest

from src.music_agent.profiles import load_profiles
from src.music_agent.scoring import (
    UserPreferences,
    recommend_songs,
    score_song,
)
from src.music_agent.track_catalog import Track, TrackCatalog


CATALOG = TrackCatalog.from_json(Path("data/tracks.json"))
PROFILES = load_profiles(Path("data/profiles.json"))


def _track(track_id: str) -> Track:
    return next(t for t in CATALOG.all_tracks if t.id == track_id)


def test_score_song_returns_consistent_numeric_score() -> None:
    prefs = UserPreferences(favorite_genres=("Lo-fi Hip Hop",), target_energy=0.3)
    scored = score_song(prefs, _track("t001"), mode="mood_first")
    assert isinstance(scored.score, float)
    assert scored.score > 0
    assert scored.reasons, "expected at least one reason"


def test_high_energy_pref_rewards_energetic_tracks() -> None:
    high_energy_prefs = UserPreferences(target_energy=0.9, favorite_moods=("energetic",))
    pop_punk = _track("t019")  # Misery Business, energy 0.92
    lofi = _track("t001")      # Aruarian Dance, energy 0.32
    high_score = score_song(high_energy_prefs, pop_punk, mode="mood_first").score
    low_score = score_song(high_energy_prefs, lofi, mode="mood_first").score
    assert high_score > low_score


def test_recommend_songs_returns_sorted_top_k() -> None:
    prefs = PROFILES["lofi_studier"]
    results = recommend_songs(prefs, CATALOG.all_tracks, top_k=5, mode="mood_first")
    assert len(results) == 5
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_genre_first_mode_filters_out_other_genres() -> None:
    prefs = UserPreferences(favorite_genres=("Lo-fi Hip Hop",), target_energy=0.3)
    results = recommend_songs(prefs, CATALOG.all_tracks, top_k=10, mode="genre_first")
    assert results, "expected lo-fi results"
    for r in results:
        assert r.track.genre == "Lo-fi Hip Hop"


def test_energy_similarity_mode_prefers_target_energy() -> None:
    prefs = UserPreferences(target_energy=0.1)  # very low energy
    results = recommend_songs(prefs, CATALOG.all_tracks, top_k=3, mode="energy_similarity")
    assert results
    # Top result should be a low-energy ambient track.
    assert results[0].track.energy <= 0.2


def test_artist_penalty_reduces_repeat_artist_dominance() -> None:
    prefs = PROFILES["cardio_edm_runner"]
    no_penalty = recommend_songs(prefs, CATALOG.all_tracks, top_k=5, mode="mood_first", artist_penalty=0)
    with_penalty = recommend_songs(prefs, CATALOG.all_tracks, top_k=5, mode="mood_first", artist_penalty=1.0)
    no_penalty_artists = [r.track.artist for r in no_penalty]
    with_penalty_artists = [r.track.artist for r in with_penalty]
    # With a strong penalty, the diversity of artists in top-5 should be at least as high.
    assert len(set(with_penalty_artists)) >= len(set(no_penalty_artists))


def test_three_profiles_produce_distinct_top_pick() -> None:
    profiles = ["lofi_studier", "cardio_edm_runner", "acoustic_indie_coffee"]
    top_picks = []
    for key in profiles:
        results = recommend_songs(PROFILES[key], CATALOG.all_tracks, top_k=3, mode="mood_first")
        assert results
        top_picks.append(results[0].track.id)
    assert len(set(top_picks)) == 3, f"expected 3 distinct top picks, got {top_picks}"


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):
        score_song(UserPreferences(), _track("t001"), mode="not_a_mode")  # type: ignore[arg-type]


def test_track_has_new_attributes() -> None:
    t = _track("t001")
    assert t.release_year > 0
    assert 0 <= t.popularity <= 100
    assert 0.0 <= t.danceability <= 1.0
    assert 0.0 <= t.instrumentalness <= 1.0
    assert t.detailed_mood_tags
