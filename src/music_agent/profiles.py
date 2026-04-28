from __future__ import annotations

import json
from pathlib import Path

from .scoring import UserPreferences


def load_profiles(path: Path) -> dict[str, UserPreferences]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles: dict[str, UserPreferences] = {}
    for key, item in raw.items():
        profiles[key] = UserPreferences(
            name=item.get("name", key),
            description=item.get("description", ""),
            favorite_genres=tuple(item.get("favorite_genres", [])),
            favorite_moods=tuple(item.get("favorite_moods", [])),
            favorite_artists=tuple(item.get("favorite_artists", [])),
            target_energy=item.get("target_energy"),
            target_valence=item.get("target_valence"),
            target_danceability=item.get("target_danceability"),
            target_acousticness=item.get("target_acousticness"),
            target_instrumentalness=item.get("target_instrumentalness"),
            tempo_range=tuple(item["tempo_range"]) if item.get("tempo_range") else None,
            decades=tuple(item.get("decades", [])),
            min_popularity=int(item.get("min_popularity", 0)),
        )
    return profiles
