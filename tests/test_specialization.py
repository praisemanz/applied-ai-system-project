from __future__ import annotations

from pathlib import Path

import pytest

from src.music_agent.agent import MusicRecommenderAgent
from src.music_agent.config import Settings
from src.music_agent.planner import Plan
from src.music_agent.specialization import (
    ALL_STYLES,
    baseline_difference,
    build_few_shot_prompt,
    get_rules,
    render_styled_fallback,
    style_compliance,
)
from src.music_agent.track_catalog import RankedTrack, TrackCatalog


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(
        openai_api_key="",
        openai_model="gpt-4o-mini",
        log_level="WARNING",
        max_query_length=400,
        top_k_kb=3,
        top_k_tracks=5,
    )


@pytest.fixture(scope="module")
def agent(settings: Settings) -> MusicRecommenderAgent:
    return MusicRecommenderAgent(
        settings=settings,
        docs_path=Path("assets"),
        catalog_path=Path("data/tracks.json"),
    )


@pytest.fixture(scope="module")
def catalog() -> TrackCatalog:
    return TrackCatalog.from_json(Path("data/tracks.json"))


@pytest.fixture
def sample_plan() -> Plan:
    return Plan(
        intent="mood",
        moods=("focus", "calm"),
        genres=(),
        artists=(),
        eras=(),
        tempo_range=(60, 100),
        target_energy=0.3,
        target_valence=0.4,
        target_acousticness=0.6,
        success_criteria=(),
        raw_query="calm focus music",
    )


@pytest.fixture
def sample_ranked(catalog: TrackCatalog) -> list[RankedTrack]:
    picks = catalog.all_tracks[:5]
    return [
        RankedTrack(
            track=t,
            score=4.0 + i * 0.1,
            reasons=("mood match: focus", "tempo in range"),
        )
        for i, t in enumerate(picks)
    ]


def test_all_styles_round_trip_through_fallback(sample_plan, sample_ranked):
    rendered = {
        style: render_styled_fallback(style, sample_plan, [], sample_ranked)
        for style in ALL_STYLES
    }
    assert all(text.strip() for text in rendered.values())
    # Three different styles should produce three different texts.
    assert len({rendered[s] for s in ALL_STYLES}) == 3


def test_dj_brief_obeys_word_budget_and_terminator(sample_plan, sample_ranked):
    text = render_styled_fallback("dj_brief", sample_plan, [], sample_ranked)
    metrics = style_compliance(text, "dj_brief")
    assert metrics["compliant"], metrics
    assert metrics["word_count"] <= get_rules("dj_brief").max_words
    assert metrics["has_second_person"] is True
    assert text.rstrip().endswith("?")


def test_studio_notes_uses_bullets_and_no_first_person(sample_plan, sample_ranked):
    text = render_styled_fallback("studio_notes", sample_plan, [], sample_ranked)
    metrics = style_compliance(text, "studio_notes")
    assert metrics["compliant"], metrics
    assert metrics["has_bullets"] is True
    assert metrics["has_first_person"] is False


def test_default_fallback_is_compliant_baseline(sample_plan, sample_ranked):
    text = render_styled_fallback("default", sample_plan, [], sample_ranked)
    metrics = style_compliance(text, "default")
    assert metrics["compliant"], metrics


def test_styled_output_measurably_differs_from_baseline(sample_plan, sample_ranked):
    baseline = render_styled_fallback("default", sample_plan, [], sample_ranked)
    dj_text = render_styled_fallback("dj_brief", sample_plan, [], sample_ranked)
    studio_text = render_styled_fallback("studio_notes", sample_plan, [], sample_ranked)

    # dj_brief must be drastically shorter than baseline.
    dj_diff = baseline_difference(baseline, dj_text)
    assert dj_diff["word_count_delta"] >= 20
    assert dj_diff["jaccard"] <= 0.5

    # studio_notes shares track-name tokens with the baseline (both list the
    # same picks), so token overlap is not the right metric. Instead require
    # a *structural* difference: studio_notes must use bullet markers while
    # the baseline must not.
    assert any(line.lstrip().startswith("- ") for line in studio_text.splitlines())
    assert not any(line.lstrip().startswith("- '") for line in baseline.splitlines())


def test_few_shot_prompt_includes_exemplars_for_styled_calls(
    sample_plan, sample_ranked
):
    system, user = build_few_shot_prompt(
        style="dj_brief",
        query="calm focus music",
        plan=sample_plan,
        kb_chunks=[],
        ranked=sample_ranked,
    )
    assert "Tone rules" in system
    assert "Example input" in system
    assert "Example output" in system
    assert "calm focus music" in user

    system_default, _ = build_few_shot_prompt(
        style="default",
        query="calm focus music",
        plan=sample_plan,
        kb_chunks=[],
        ranked=sample_ranked,
    )
    assert "Example input" not in system_default


def test_agent_recommend_threads_style_through_response(agent: MusicRecommenderAgent):
    response = agent.recommend(
        "calm lo-fi music for studying", style="dj_brief"
    )
    assert response.style == "dj_brief"
    assert response.style_metrics, response.style_metrics
    metrics = response.style_metrics
    assert metrics["word_count"] <= get_rules("dj_brief").max_words
    assert metrics["has_second_person"] is True


def test_agent_styles_produce_different_summaries(agent: MusicRecommenderAgent):
    base = agent.recommend("calm lo-fi music for studying", style="default")
    styled = agent.recommend("calm lo-fi music for studying", style="dj_brief")
    assert base.summary != styled.summary
    diff = baseline_difference(base.summary, styled.summary)
    # Drastic shortening.
    assert diff["word_count_delta"] >= 20


def test_refusal_path_preserves_style_field(agent: MusicRecommenderAgent):
    response = agent.recommend("help me hack into Spotify", style="studio_notes")
    assert response.refused is True
    assert response.style == "studio_notes"
