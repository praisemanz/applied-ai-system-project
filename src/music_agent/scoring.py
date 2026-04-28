"""Public scoring API for the music recommender.

This module exposes the rubric-required functions:
    score_song(user_prefs, song, mode)         -> ScoredSong
    recommend_songs(user_prefs, songs, ...)    -> list[ScoredSong]

It supports three ranking modes (Genre-First, Mood-First, Energy-Similarity)
and an artist-diversity penalty to reduce filter-bubble effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .track_catalog import Track


RankingMode = Literal["mood_first", "genre_first", "energy_similarity"]
ALL_MODES: tuple[RankingMode, ...] = ("mood_first", "genre_first", "energy_similarity")


@dataclass(frozen=True)
class UserPreferences:
    name: str = "custom"
    description: str = ""
    favorite_genres: tuple[str, ...] = ()
    favorite_moods: tuple[str, ...] = ()
    favorite_artists: tuple[str, ...] = ()
    target_energy: float | None = None
    target_valence: float | None = None
    target_danceability: float | None = None
    target_acousticness: float | None = None
    target_instrumentalness: float | None = None
    tempo_range: tuple[int, int] | None = None
    decades: tuple[str, ...] = ()
    min_popularity: int = 0


@dataclass(frozen=True)
class ScoredSong:
    track: Track
    score: float
    reasons: tuple[str, ...] = field(default=())


def score_song(
    prefs: UserPreferences,
    song: Track,
    mode: RankingMode = "mood_first",
) -> ScoredSong:
    """Score a single song against a user's preferences using the chosen mode.

    Returns a ScoredSong with a numeric score and a list of human-readable
    reasons. Higher scores are better. Scores can be negative for poor fits.
    """
    if mode == "mood_first":
        score, reasons = _score_mood_first(prefs, song)
    elif mode == "genre_first":
        score, reasons = _score_genre_first(prefs, song)
    elif mode == "energy_similarity":
        score, reasons = _score_energy_similarity(prefs, song)
    else:
        raise ValueError(f"Unknown ranking mode: {mode}")
    return ScoredSong(track=song, score=round(score, 3), reasons=tuple(reasons))


def recommend_songs(
    prefs: UserPreferences,
    songs: list[Track],
    top_k: int = 5,
    mode: RankingMode = "mood_first",
    artist_penalty: float = 0.5,
) -> list[ScoredSong]:
    """Score every song, apply optional artist-diversity penalty, and return top_k.

    artist_penalty: how much to subtract from the score of each subsequent track
    by an artist already represented above it. 0 disables the penalty. The
    penalty is applied during a re-ranking pass so the *first* track by an
    artist keeps its full score.
    """
    if top_k <= 0:
        return []

    scored = [score_song(prefs, song, mode=mode) for song in songs]
    scored = [s for s in scored if s.score > 0]
    scored.sort(key=lambda s: s.score, reverse=True)

    if artist_penalty <= 0:
        return scored[:top_k]

    final: list[ScoredSong] = []
    artist_counts: dict[str, int] = {}
    for s in scored:
        seen = artist_counts.get(s.track.artist, 0)
        if seen == 0:
            final.append(s)
        else:
            adjusted = round(s.score - (artist_penalty * seen), 3)
            extra_reason = f"artist diversity penalty x{seen}"
            final.append(
                ScoredSong(
                    track=s.track,
                    score=adjusted,
                    reasons=tuple(list(s.reasons) + [extra_reason]),
                )
            )
        artist_counts[s.track.artist] = seen + 1

    final.sort(key=lambda s: s.score, reverse=True)
    return final[:top_k]


def _score_mood_first(prefs: UserPreferences, song: Track) -> tuple[float, list[str]]:
    """Mood-first: weight mood overlap highest, then features and genre."""
    score = 0.0
    reasons: list[str] = []

    if prefs.favorite_moods:
        track_moods = {m.lower() for m in song.moods}
        overlap = [m for m in prefs.favorite_moods if m.lower() in track_moods]
        if overlap:
            score += 1.5 * len(overlap)
            reasons.append(f"mood match: {', '.join(overlap)}")

    if prefs.favorite_genres:
        if any(g.lower() == song.genre.lower() for g in prefs.favorite_genres):
            score += 1.5
            reasons.append(f"genre match: {song.genre}")

    if prefs.favorite_artists:
        if any(a.lower() == song.artist.lower() for a in prefs.favorite_artists):
            score += 2.0
            reasons.append(f"artist match: {song.artist}")

    score += _feature_score(prefs, song, weights=_MOOD_FIRST_WEIGHTS, reasons=reasons)
    score += _meta_score(prefs, song, reasons)
    return score, reasons


def _score_genre_first(prefs: UserPreferences, song: Track) -> tuple[float, list[str]]:
    """Genre-first: hard-prefer favorite genres; only fall back to others if no genre set."""
    score = 0.0
    reasons: list[str] = []

    if prefs.favorite_genres:
        if any(g.lower() == song.genre.lower() for g in prefs.favorite_genres):
            score += 3.0
            reasons.append(f"genre match: {song.genre}")
        else:
            return -1.0, ["genre mismatch (filtered out)"]

    if prefs.favorite_artists:
        if any(a.lower() == song.artist.lower() for a in prefs.favorite_artists):
            score += 1.5
            reasons.append(f"artist match: {song.artist}")

    if prefs.favorite_moods:
        track_moods = {m.lower() for m in song.moods}
        overlap = [m for m in prefs.favorite_moods if m.lower() in track_moods]
        if overlap:
            score += 0.7 * len(overlap)
            reasons.append(f"mood match: {', '.join(overlap)}")

    score += _feature_score(prefs, song, weights=_GENRE_FIRST_WEIGHTS, reasons=reasons)
    score += _meta_score(prefs, song, reasons)
    return score, reasons


def _score_energy_similarity(prefs: UserPreferences, song: Track) -> tuple[float, list[str]]:
    """Energy-similarity: rank purely by closeness to target audio features."""
    score = 0.0
    reasons: list[str] = []

    target_energy = prefs.target_energy if prefs.target_energy is not None else 0.5
    energy_fit = 1 - abs(song.energy - target_energy)
    score += 3.0 * energy_fit
    reasons.append(f"energy fit {round(energy_fit, 2)} (target {target_energy})")

    if prefs.target_valence is not None:
        valence_fit = 1 - abs(song.valence - prefs.target_valence)
        score += 1.0 * valence_fit
        reasons.append(f"valence fit {round(valence_fit, 2)}")

    if prefs.target_danceability is not None:
        d_fit = 1 - abs(song.danceability - prefs.target_danceability)
        score += 0.8 * d_fit
        reasons.append(f"danceability fit {round(d_fit, 2)}")

    if prefs.tempo_range is not None:
        low, high = prefs.tempo_range
        if low <= song.tempo_bpm <= high:
            score += 0.5
            reasons.append(f"tempo {song.tempo_bpm} BPM in range")
        else:
            score -= 0.5

    score += _meta_score(prefs, song, reasons)
    return score, reasons


_MOOD_FIRST_WEIGHTS = {
    "energy": 1.0,
    "valence": 1.0,
    "acousticness": 0.6,
    "danceability": 0.6,
    "instrumentalness": 0.4,
}

_GENRE_FIRST_WEIGHTS = {
    "energy": 0.6,
    "valence": 0.6,
    "acousticness": 0.4,
    "danceability": 0.4,
    "instrumentalness": 0.3,
}


def _feature_score(
    prefs: UserPreferences,
    song: Track,
    weights: dict[str, float],
    reasons: list[str],
) -> float:
    score = 0.0
    if prefs.target_energy is not None:
        fit = 1 - abs(song.energy - prefs.target_energy)
        score += weights["energy"] * fit
    if prefs.target_valence is not None:
        fit = 1 - abs(song.valence - prefs.target_valence)
        score += weights["valence"] * fit
    if prefs.target_acousticness is not None:
        fit = 1 - abs(song.acousticness - prefs.target_acousticness)
        score += weights["acousticness"] * fit
    if prefs.target_danceability is not None:
        fit = 1 - abs(song.danceability - prefs.target_danceability)
        score += weights["danceability"] * fit
    if prefs.target_instrumentalness is not None:
        fit = 1 - abs(song.instrumentalness - prefs.target_instrumentalness)
        score += weights["instrumentalness"] * fit
    if prefs.tempo_range is not None:
        low, high = prefs.tempo_range
        if low <= song.tempo_bpm <= high:
            score += 0.5
            reasons.append(f"tempo {song.tempo_bpm} BPM in range")
        else:
            score -= 0.3
    return score


def _meta_score(prefs: UserPreferences, song: Track, reasons: list[str]) -> float:
    score = 0.0
    if prefs.decades:
        if song.era in prefs.decades:
            score += 0.5
            reasons.append(f"decade match: {song.era}")
    if prefs.min_popularity and song.popularity >= prefs.min_popularity:
        score += 0.4
        reasons.append(f"popularity {song.popularity} >= min")
    elif prefs.min_popularity and song.popularity < prefs.min_popularity:
        score -= 0.5
    return score
