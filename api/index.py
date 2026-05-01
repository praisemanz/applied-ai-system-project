from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
import sys
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.music_agent.agent import MusicRecommenderAgent  # noqa: E402
from src.music_agent.config import get_settings  # noqa: E402
from src.music_agent.profiles import load_profiles  # noqa: E402
from src.music_agent.scoring import ALL_MODES, ScoredSong, recommend_songs  # noqa: E402
from src.music_agent.track_catalog import TrackCatalog  # noqa: E402

SummaryStyle = Literal["default", "dj_brief", "studio_notes"]


class RecommendRequest(BaseModel):
    query: str | None = None
    profile: str | None = None
    mode: str = "mood_first"
    style: SummaryStyle = "default"
    top_k: int = Field(default=5, ge=1, le=10)
    artist_penalty: float = Field(default=0.5, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def validate_source(self) -> "RecommendRequest":
        if bool(self.query) == bool(self.profile):
            raise ValueError("Provide exactly one of: query or profile.")
        if self.mode not in ALL_MODES:
            raise ValueError(f"Invalid mode '{self.mode}'. Valid modes: {', '.join(ALL_MODES)}")
        return self


def _scored_to_payload(scored: list[ScoredSong]) -> list[dict[str, Any]]:
    return [
        {
            "id": s.track.id,
            "title": s.track.title,
            "artist": s.track.artist,
            "genre": s.track.genre,
            "tempo_bpm": s.track.tempo_bpm,
            "energy": s.track.energy,
            "valence": s.track.valence,
            "acousticness": s.track.acousticness,
            "danceability": s.track.danceability,
            "instrumentalness": s.track.instrumentalness,
            "popularity": s.track.popularity,
            "score": s.score,
            "reasons": list(s.reasons),
        }
        for s in scored
    ]


@lru_cache(maxsize=1)
def _agent() -> MusicRecommenderAgent:
    settings = get_settings()
    return MusicRecommenderAgent(
        settings=settings,
        docs_path=PROJECT_ROOT / "assets",
        catalog_path=PROJECT_ROOT / "data" / "tracks.json",
    )


@lru_cache(maxsize=1)
def _profiles():
    return load_profiles(PROJECT_ROOT / "data" / "profiles.json")


@lru_cache(maxsize=1)
def _catalog():
    return TrackCatalog.from_json(PROJECT_ROOT / "data" / "tracks.json")


app = FastAPI(title="TuneSage API", version="1.0.0")


@app.exception_handler(Exception)
def _unhandled_exception(_request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "error_type": type(exc).__name__},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "tunesage-api",
        "modes": list(ALL_MODES),
        "styles": ["default", "dj_brief", "studio_notes"],
    }


@app.get("/api/profiles")
def profiles() -> dict[str, Any]:
    data = _profiles()
    return {
        "profiles": [
            {
                "key": key,
                "name": prefs.name,
                "description": prefs.description,
                "favorite_genres": list(prefs.favorite_genres),
                "favorite_moods": list(prefs.favorite_moods),
                "tempo_range": list(prefs.tempo_range) if prefs.tempo_range else None,
                "target_energy": prefs.target_energy,
                "target_valence": prefs.target_valence,
            }
            for key, prefs in data.items()
        ]
    }


@app.post("/api/recommend")
def recommend(payload: RecommendRequest) -> dict[str, Any]:
    if payload.query:
        try:
            response = _agent().recommend(
                query=payload.query,
                mode=payload.mode,  # type: ignore[arg-type]
                artist_penalty=payload.artist_penalty,
                style=payload.style,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "intent": response.intent,
            "refused": response.refused,
            "summary": response.summary,
            "confidence": response.confidence,
            "passed_checks": response.passed_checks,
            "checker_reasons": response.checker_reasons,
            "style": response.style,
            "style_metrics": response.style_metrics,
            "citations": response.citations,
            "recommendations": [asdict(r) for r in response.recommendations],
        }

    profiles_map = _profiles()
    if payload.profile not in profiles_map:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown profile '{payload.profile}'.",
        )

    prefs = profiles_map[payload.profile]
    scored = recommend_songs(
        prefs=prefs,
        songs=_catalog().all_tracks,
        top_k=payload.top_k,
        mode=payload.mode,  # type: ignore[arg-type]
        artist_penalty=payload.artist_penalty,
    )

    return {
        "profile": payload.profile,
        "profile_name": prefs.name,
        "mode": payload.mode,
        "style": payload.style,
        "recommendations": _scored_to_payload(scored),
    }
