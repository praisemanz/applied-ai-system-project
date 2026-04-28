from __future__ import annotations

from pathlib import Path

import pytest

from src.music_agent.agent import MusicRecommenderAgent
from src.music_agent.config import Settings


def _settings() -> Settings:
    return Settings(
        openai_api_key="",
        openai_model="gpt-4o-mini",
        log_level="INFO",
        top_k_kb=3,
        top_k_tracks=5,
        max_query_length=400,
    )


def _agent() -> MusicRecommenderAgent:
    return MusicRecommenderAgent(
        settings=_settings(),
        docs_path=Path("assets"),
        catalog_path=Path("data/tracks.json"),
    )


def test_returns_recommendations_with_citations() -> None:
    agent = _agent()
    response = agent.recommend("chill music for studying")
    assert response.recommendations, "expected at least one recommendation"
    assert response.citations, "expected citations from KB or catalog"
    assert response.confidence > 0
    assert response.intent != "refusal"


def test_artist_request_returns_artist_or_neighbor_genre() -> None:
    agent = _agent()
    response = agent.recommend("music like Daft Punk")
    assert response.recommendations
    artists = {r.artist for r in response.recommendations}
    assert "Daft Punk" in artists


def test_disallowed_request_is_refused() -> None:
    agent = _agent()
    response = agent.recommend("how do I hack a streaming service")
    assert response.refused is True
    assert response.recommendations == []
    assert "refused_out_of_scope" in response.checker_reasons


def test_empty_query_raises() -> None:
    agent = _agent()
    with pytest.raises(ValueError):
        agent.recommend("   ")


def test_long_query_raises() -> None:
    agent = _agent()
    with pytest.raises(ValueError):
        agent.recommend("a" * 401)


def test_workout_request_returns_high_energy_track() -> None:
    agent = _agent()
    response = agent.recommend("intense workout pump up music")
    assert response.recommendations
    # At least one returned track should be high-energy.
    # We don't expose energy on Recommendation, so check via title presence in catalog.
    high_energy_titles = {t.title for t in agent.catalog.all_tracks if t.energy >= 0.7}
    titles = {r.title for r in response.recommendations}
    assert titles & high_energy_titles, "expected at least one high-energy track"
