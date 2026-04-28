from __future__ import annotations

from dataclasses import dataclass
import re

from .track_catalog import TrackCatalog, TrackQuery


MOOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "focus": ("focus", "study", "studying", "concentrate", "concentration", "work", "reading"),
    "calm": ("calm", "chill", "relax", "relaxing", "mellow", "quiet", "peaceful", "sleep"),
    "energetic": ("energetic", "energy", "pump", "hype", "workout", "running", "gym", "intense"),
    "party": ("party", "dance", "dancing", "club", "festival", "celebration"),
    "melancholic": ("sad", "melancholy", "melancholic", "heartbreak", "lonely", "blue"),
    "reflective": ("reflective", "thoughtful", "introspective", "deep", "meditative"),
    "uplifting": ("happy", "uplifting", "joyful", "cheerful", "optimistic", "feel good", "feel-good"),
    "romantic": ("romantic", "love", "intimate", "date", "candlelit"),
    "nostalgic": ("nostalgic", "nostalgia", "retro", "throwback", "memory", "memories"),
    "cinematic": ("cinematic", "soundtrack", "movie", "film"),
    "groove": ("groovy", "groove", "funky", "funk"),
    "defiant": ("angry", "angsty", "defiant", "rebellious"),
}


ERA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "1960s": ("60s", "1960s", "sixties"),
    "1970s": ("70s", "1970s", "seventies"),
    "1980s": ("80s", "1980s", "eighties"),
    "1990s": ("90s", "1990s", "nineties"),
    "2000s": ("00s", "2000s"),
    "2010s": ("10s", "2010s"),
}


MOOD_TARGETS: dict[str, dict[str, float]] = {
    "focus":       {"energy": 0.30, "valence": 0.45, "acousticness": 0.55},
    "calm":        {"energy": 0.25, "valence": 0.50, "acousticness": 0.60},
    "energetic":   {"energy": 0.85, "valence": 0.70},
    "party":       {"energy": 0.85, "valence": 0.80},
    "melancholic": {"energy": 0.30, "valence": 0.25, "acousticness": 0.60},
    "reflective":  {"energy": 0.35, "valence": 0.40, "acousticness": 0.55},
    "uplifting":   {"energy": 0.65, "valence": 0.80},
    "romantic":    {"energy": 0.45, "valence": 0.70, "acousticness": 0.55},
    "nostalgic":   {"energy": 0.55, "valence": 0.45},
    "cinematic":   {"energy": 0.50, "valence": 0.45},
    "groove":      {"energy": 0.65, "valence": 0.70},
    "defiant":     {"energy": 0.85, "valence": 0.55},
}


MOOD_TEMPO_RANGES: dict[str, tuple[int, int]] = {
    "focus":       (60, 100),
    "calm":        (50, 100),
    "energetic":   (130, 185),
    "party":       (115, 135),
    "melancholic": (60, 110),
    "uplifting":   (95, 130),
    "romantic":    (75, 120),
}


@dataclass(frozen=True)
class Plan:
    intent: str
    moods: tuple[str, ...]
    genres: tuple[str, ...]
    artists: tuple[str, ...]
    eras: tuple[str, ...]
    tempo_range: tuple[int, int] | None
    target_energy: float | None
    target_valence: float | None
    target_acousticness: float | None
    success_criteria: tuple[str, ...]
    raw_query: str

    def to_track_query(self) -> TrackQuery:
        return TrackQuery(
            moods=self.moods,
            genres=self.genres,
            artists=self.artists,
            eras=self.eras,
            tempo_range=self.tempo_range,
            target_energy=self.target_energy,
            target_valence=self.target_valence,
            target_acousticness=self.target_acousticness,
        )


def build_plan(query: str, catalog: TrackCatalog) -> Plan:
    lowered = query.lower()

    detected_moods: list[str] = []
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(_word_in(kw, lowered) for kw in keywords):
            detected_moods.append(mood)

    detected_genres: list[str] = []
    for genre in sorted(catalog.genres(), key=len, reverse=True):
        if genre.lower() in lowered:
            detected_genres.append(genre)

    detected_artists: list[str] = []
    for artist in sorted(catalog.artists(), key=len, reverse=True):
        if artist.lower() in lowered:
            detected_artists.append(artist)

    detected_eras: list[str] = []
    for era, keywords in ERA_KEYWORDS.items():
        if any(_word_in(kw, lowered) for kw in keywords):
            detected_eras.append(era)

    intent = _resolve_intent(detected_moods, detected_genres, detected_artists)

    target_energy: float | None = None
    target_valence: float | None = None
    target_acousticness: float | None = None
    tempo_range: tuple[int, int] | None = None
    for mood in detected_moods:
        targets = MOOD_TARGETS.get(mood, {})
        if "energy" in targets and target_energy is None:
            target_energy = targets["energy"]
        if "valence" in targets and target_valence is None:
            target_valence = targets["valence"]
        if "acousticness" in targets and target_acousticness is None:
            target_acousticness = targets["acousticness"]
        if mood in MOOD_TEMPO_RANGES and tempo_range is None:
            tempo_range = MOOD_TEMPO_RANGES[mood]

    explicit_tempo = _parse_tempo(lowered)
    if explicit_tempo is not None:
        tempo_range = explicit_tempo

    success_criteria: list[str] = ["Return tracks grounded in the local catalog."]
    if detected_moods:
        success_criteria.append(f"Recommendations should fit mood: {', '.join(detected_moods)}.")
    if detected_genres:
        success_criteria.append(f"Recommendations should be in genre: {', '.join(detected_genres)}.")
    if detected_artists:
        success_criteria.append(f"Highlight tracks by or similar to: {', '.join(detected_artists)}.")
    if tempo_range is not None:
        success_criteria.append(f"Tempo should sit between {tempo_range[0]} and {tempo_range[1]} BPM.")

    return Plan(
        intent=intent,
        moods=tuple(detected_moods),
        genres=tuple(detected_genres),
        artists=tuple(detected_artists),
        eras=tuple(detected_eras),
        tempo_range=tempo_range,
        target_energy=target_energy,
        target_valence=target_valence,
        target_acousticness=target_acousticness,
        success_criteria=tuple(success_criteria),
        raw_query=query,
    )


def _resolve_intent(moods: list[str], genres: list[str], artists: list[str]) -> str:
    if artists:
        return "similar_artist"
    if genres and moods:
        return "genre_and_mood"
    if genres:
        return "genre"
    if moods:
        return "mood"
    return "open_ended"


def _word_in(token: str, text: str) -> bool:
    if " " in token or "-" in token:
        return token in text
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def _parse_tempo(text: str) -> tuple[int, int] | None:
    match = re.search(r"(\d{2,3})\s*(?:to|-|–)\s*(\d{2,3})\s*bpm", text)
    if match:
        low, high = sorted([int(match.group(1)), int(match.group(2))])
        return (low, high)
    return None
