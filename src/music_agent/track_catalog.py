from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    genre: str
    moods: tuple[str, ...]
    tempo_bpm: int
    energy: float
    valence: float
    acousticness: float
    era: str
    description: str
    release_year: int = 0
    popularity: int = 0
    danceability: float = 0.0
    instrumentalness: float = 0.0
    detailed_mood_tags: tuple[str, ...] = ()

    def cite(self) -> str:
        return f"{self.title} - {self.artist}"


@dataclass(frozen=True)
class TrackQuery:
    moods: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    artists: tuple[str, ...] = ()
    eras: tuple[str, ...] = ()
    tempo_range: tuple[int, int] | None = None
    target_energy: float | None = None
    target_valence: float | None = None
    target_acousticness: float | None = None
    target_danceability: float | None = None
    target_instrumentalness: float | None = None
    min_popularity: int = 0


@dataclass(frozen=True)
class RankedTrack:
    track: Track
    score: float
    reasons: tuple[str, ...] = field(default=())


class TrackCatalog:
    def __init__(self, tracks: list[Track]) -> None:
        self._tracks = tracks

    @classmethod
    def from_json(cls, path: Path) -> "TrackCatalog":
        raw = json.loads(path.read_text(encoding="utf-8"))
        tracks = [
            Track(
                id=item["id"],
                title=item["title"],
                artist=item["artist"],
                genre=item["genre"],
                moods=tuple(item.get("moods", [])),
                tempo_bpm=int(item["tempo_bpm"]),
                energy=float(item["energy"]),
                valence=float(item["valence"]),
                acousticness=float(item["acousticness"]),
                era=item["era"],
                description=item["description"],
                release_year=int(item.get("release_year", 0)),
                popularity=int(item.get("popularity", 0)),
                danceability=float(item.get("danceability", 0.0)),
                instrumentalness=float(item.get("instrumentalness", 0.0)),
                detailed_mood_tags=tuple(item.get("detailed_mood_tags", [])),
            )
            for item in raw
        ]
        return cls(tracks)

    @property
    def all_tracks(self) -> list[Track]:
        return list(self._tracks)

    def genres(self) -> set[str]:
        return {t.genre for t in self._tracks}

    def artists(self) -> set[str]:
        return {t.artist for t in self._tracks}

    def search(self, query: TrackQuery, top_k: int) -> list[RankedTrack]:
        scored: list[RankedTrack] = []
        for track in self._tracks:
            score, reasons = self._score(track, query)
            if score <= 0:
                continue
            scored.append(RankedTrack(track=track, score=score, reasons=tuple(reasons)))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _score(track: Track, query: TrackQuery) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        if query.genres:
            if any(g.lower() == track.genre.lower() for g in query.genres):
                score += 2.0
                reasons.append(f"matches genre {track.genre}")
            else:
                return 0.0, []

        if query.artists:
            if any(a.lower() == track.artist.lower() for a in query.artists):
                score += 2.5
                reasons.append(f"matches artist {track.artist}")

        if query.moods:
            track_moods = {m.lower() for m in track.moods}
            overlap = [m for m in query.moods if m.lower() in track_moods]
            if overlap:
                score += 1.5 * len(overlap)
                reasons.append(f"mood match: {', '.join(overlap)}")
            elif not query.artists:
                return 0.0, []

        if query.eras:
            if any(e.lower() == track.era.lower() for e in query.eras):
                score += 1.0
                reasons.append(f"era match: {track.era}")

        if query.tempo_range is not None:
            low, high = query.tempo_range
            if low <= track.tempo_bpm <= high:
                score += 0.8
                reasons.append(f"tempo {track.tempo_bpm} BPM in range")
            else:
                score -= 0.4

        if query.target_energy is not None:
            score += 1.0 * (1 - abs(track.energy - query.target_energy))
        if query.target_valence is not None:
            score += 1.0 * (1 - abs(track.valence - query.target_valence))
        if query.target_acousticness is not None:
            score += 0.6 * (1 - abs(track.acousticness - query.target_acousticness))
        if query.target_danceability is not None:
            score += 0.8 * (1 - abs(track.danceability - query.target_danceability))
        if query.target_instrumentalness is not None:
            score += 0.5 * (1 - abs(track.instrumentalness - query.target_instrumentalness))

        if query.min_popularity > 0 and track.popularity < query.min_popularity:
            score -= 0.5

        return score, reasons
