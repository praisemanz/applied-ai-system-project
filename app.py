"""TuneSage Streamlit UI.

A polished web front-end for the agentic music recommender. Wraps the same
agent, scoring API, profiles, and specialization styles exposed by the CLI,
adding catalog browsing, profile comparison, and live trace inspection.

Run from the project root:

    streamlit run app.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.music_agent.agent import AgentResponse, MusicRecommenderAgent  # noqa: E402
from src.music_agent.config import get_settings  # noqa: E402
from src.music_agent.logging_utils import configure_logging  # noqa: E402
from src.music_agent.planner import Plan  # noqa: E402
from src.music_agent.profiles import load_profiles  # noqa: E402
from src.music_agent.scoring import (  # noqa: E402
    ALL_MODES,
    ScoredSong,
    UserPreferences,
    recommend_songs,
)
from src.music_agent.specialization import (  # noqa: E402
    ALL_STYLES,
    render_styled_fallback,
    style_compliance,
)
from src.music_agent.track_catalog import RankedTrack, Track, TrackCatalog  # noqa: E402


# ---------------------------------------------------------------------------
# Page config + CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="TuneSage — Agentic Music Recommender",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root {
    --ts-bg: #0b0b14;
    --ts-panel: #15152a;
    --ts-panel-2: #1c1c36;
    --ts-border: rgba(167, 139, 250, 0.18);
    --ts-text: #ececf5;
    --ts-muted: #9b9bb8;
    --ts-accent: #a78bfa;
    --ts-accent-2: #38bdf8;
    --ts-accent-3: #f472b6;
    --ts-success: #34d399;
    --ts-warning: #fbbf24;
    --ts-danger: #f87171;
}

html, body, [data-testid="stAppViewContainer"] {
    background:
      radial-gradient(1200px 600px at 10% -10%, rgba(167,139,250,0.18), transparent 60%),
      radial-gradient(900px 500px at 110% 0%, rgba(56,189,248,0.12), transparent 60%),
      var(--ts-bg);
    color: var(--ts-text);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0f1f 0%, #15152a 100%);
    border-right: 1px solid var(--ts-border);
}

.ts-hero {
    padding: 28px 32px;
    border-radius: 18px;
    background: linear-gradient(135deg,
        rgba(167,139,250,0.18) 0%,
        rgba(56,189,248,0.10) 50%,
        rgba(244,114,182,0.14) 100%);
    border: 1px solid var(--ts-border);
    margin-bottom: 22px;
    box-shadow: 0 12px 40px -16px rgba(167,139,250,0.35);
}
.ts-hero h1 {
    font-size: 2.4rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #ffffff 0%, #c4b5fd 50%, #7dd3fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ts-hero p {
    margin: 6px 0 0;
    color: var(--ts-muted);
    font-size: 1.02rem;
    max-width: 820px;
}
.ts-hero .ts-tagchip {
    display: inline-block;
    padding: 4px 10px;
    margin-right: 8px;
    margin-top: 12px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    background: rgba(167,139,250,0.16);
    border: 1px solid var(--ts-border);
    color: #ddd6fe;
}

.ts-card {
    background: linear-gradient(180deg, var(--ts-panel) 0%, var(--ts-panel-2) 100%);
    border: 1px solid var(--ts-border);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
    transition: transform 120ms ease, border-color 120ms ease;
}
.ts-card:hover {
    transform: translateY(-1px);
    border-color: rgba(167,139,250,0.45);
}

.ts-rank {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px; height: 32px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 0.95rem;
    background: linear-gradient(135deg, var(--ts-accent) 0%, var(--ts-accent-2) 100%);
    color: #0b0b14;
    margin-right: 12px;
}

.ts-title { font-size: 1.15rem; font-weight: 600; color: var(--ts-text); }
.ts-artist { color: var(--ts-muted); font-size: 0.92rem; }

.ts-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 600;
    background: rgba(56,189,248,0.12);
    border: 1px solid rgba(56,189,248,0.35);
    color: #7dd3fc;
    margin-right: 6px;
}
.ts-pill.mood    { background: rgba(244,114,182,0.10); border-color: rgba(244,114,182,0.35); color: #fbcfe8; }
.ts-pill.score   { background: rgba(52,211,153,0.10); border-color: rgba(52,211,153,0.35); color: #6ee7b7; }
.ts-pill.tempo   { background: rgba(251,191,36,0.10); border-color: rgba(251,191,36,0.35); color: #fde68a; }
.ts-pill.energy  { background: rgba(167,139,250,0.10); border-color: rgba(167,139,250,0.35); color: #ddd6fe; }
.ts-pill.year    { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.10); color: #d1d5db; }

.ts-why {
    color: var(--ts-muted);
    font-size: 0.9rem;
    margin-top: 8px;
    font-style: italic;
    border-left: 2px solid rgba(167,139,250,0.45);
    padding-left: 10px;
}

.ts-bar {
    height: 6px; border-radius: 3px;
    background: rgba(255,255,255,0.06);
    overflow: hidden;
    margin-top: 6px;
}
.ts-bar > span {
    display:block; height: 100%;
    background: linear-gradient(90deg, var(--ts-accent) 0%, var(--ts-accent-2) 100%);
}

.ts-summary-box {
    background: rgba(167,139,250,0.06);
    border: 1px solid var(--ts-border);
    border-radius: 14px;
    padding: 18px 20px;
    margin-top: 10px;
    font-size: 0.97rem;
    line-height: 1.55;
    color: #e9e9f5;
    white-space: pre-wrap;
}

.ts-section-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--ts-muted);
    margin: 14px 0 6px;
    font-weight: 600;
}

.ts-citation {
    display: inline-block;
    padding: 4px 10px;
    margin: 4px 6px 0 0;
    border-radius: 8px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    color: #cbd5e1;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.78rem;
}

.ts-refusal {
    border: 1px solid rgba(248,113,113,0.45);
    background: rgba(248,113,113,0.07);
    color: #fecaca;
    border-radius: 12px;
    padding: 14px 18px;
}

.ts-status {
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 0.85rem; font-weight: 600;
    padding: 6px 12px; border-radius: 999px;
    background: rgba(52,211,153,0.10);
    color: #6ee7b7;
    border: 1px solid rgba(52,211,153,0.35);
}
.ts-status.warn   { background: rgba(251,191,36,0.10); color: #fde68a; border-color: rgba(251,191,36,0.35); }
.ts-status.danger { background: rgba(248,113,113,0.10); color: #fecaca; border-color: rgba(248,113,113,0.35); }

.ts-profile-card {
    background: linear-gradient(160deg, rgba(167,139,250,0.10) 0%, rgba(56,189,248,0.06) 100%);
    border: 1px solid var(--ts-border);
    border-radius: 16px;
    padding: 18px 20px;
    height: 100%;
}

div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

button[kind="primary"] {
    background: linear-gradient(135deg, var(--ts-accent) 0%, var(--ts-accent-2) 100%) !important;
    color: #0b0b14 !important;
    border: 0 !important;
    font-weight: 600 !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_settings_cached():
    s = get_settings()
    configure_logging(s.log_level)
    return s


@st.cache_resource(show_spinner=False)
def get_agent() -> MusicRecommenderAgent:
    settings = get_settings_cached()
    return MusicRecommenderAgent(
        settings=settings,
        docs_path=PROJECT_ROOT / "assets",
        catalog_path=PROJECT_ROOT / "data" / "tracks.json",
    )


@st.cache_resource(show_spinner=False)
def get_catalog() -> TrackCatalog:
    return TrackCatalog.from_json(PROJECT_ROOT / "data" / "tracks.json")


@st.cache_resource(show_spinner=False)
def get_profiles() -> dict[str, UserPreferences]:
    return load_profiles(PROJECT_ROOT / "data" / "profiles.json")


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _bar(value: float, max_value: float = 1.0) -> str:
    pct = max(0.0, min(1.0, value / max_value)) * 100
    return f'<div class="ts-bar"><span style="width:{pct:.0f}%"></span></div>'


def render_track_card(rank: int, track: Track, score: float, reasons: tuple[str, ...]) -> None:
    moods_html = " ".join(f'<span class="ts-pill mood">{m}</span>' for m in track.moods[:3])
    why = "; ".join(reasons) if reasons else "matches request profile"
    html = f"""
    <div class="ts-card">
      <div style="display:flex; align-items:flex-start;">
        <div class="ts-rank">{rank}</div>
        <div style="flex:1;">
          <div class="ts-title">{track.title}</div>
          <div class="ts-artist">{track.artist} · {track.genre} · {track.era}</div>
          <div style="margin-top:10px;">
            <span class="ts-pill score">score {score:.2f}</span>
            <span class="ts-pill tempo">{track.tempo_bpm} BPM</span>
            <span class="ts-pill energy">energy {track.energy:.2f}</span>
            <span class="ts-pill year">{track.release_year or track.era}</span>
            {moods_html}
          </div>
          <div class="ts-why">{why}</div>
        </div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_summary(summary: str) -> None:
    if not summary.strip():
        return
    st.markdown('<div class="ts-section-label">Agent summary</div>', unsafe_allow_html=True)
    safe = summary.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(f'<div class="ts-summary-box">{safe}</div>', unsafe_allow_html=True)


def render_citations(citations: list[str]) -> None:
    if not citations:
        return
    st.markdown('<div class="ts-section-label">Grounded citations</div>', unsafe_allow_html=True)
    chips = "".join(f'<span class="ts-citation">{c}</span>' for c in citations)
    st.markdown(chips, unsafe_allow_html=True)


def render_confidence(confidence: float, passed: bool, reasons: list[str]) -> None:
    status_cls = "" if passed else "warn"
    status_text = "Checks passed" if passed else "Checks: " + ", ".join(reasons or ["unknown"])
    st.markdown(
        f'<div class="ts-status {status_cls}">Confidence {confidence:.2f} · {status_text}</div>',
        unsafe_allow_html=True,
    )


def render_style_metrics(style: str, metrics: dict[str, Any]) -> None:
    if style == "default" or not metrics:
        return
    cols = st.columns(4)
    cols[0].metric("Words", metrics.get("word_count", "—"))
    cols[1].metric("Second person", "yes" if metrics.get("has_second_person") else "no")
    cols[2].metric("Bullets", "yes" if metrics.get("has_bullets") else "no")
    cols[3].metric("Compliant", "yes" if metrics.get("compliant") else "no")


def render_recommendations(
    recommendations: list[Any],
    catalog_index: dict[str, Track],
) -> None:
    for i, rec in enumerate(recommendations, start=1):
        track = catalog_index.get(getattr(rec, "track_id", None))
        if track is None:
            track = Track(
                id="?", title=rec.title, artist=rec.artist, genre=rec.genre,
                moods=(), tempo_bpm=0, energy=0.0, valence=0.0, acousticness=0.0,
                era="", description="",
            )
        render_track_card(i, track, rec.score, tuple([rec.why]))


def render_scored_recommendations(scored: list[ScoredSong]) -> None:
    for i, s in enumerate(scored, start=1):
        render_track_card(i, s.track, s.score, s.reasons)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> dict[str, Any]:
    with st.sidebar:
        st.markdown("### TuneSage")
        st.caption("Agentic music recommender · RAG · Plan / Check / Revise")

        settings = get_settings_cached()
        if settings.openai_api_key:
            st.markdown(
                '<div class="ts-status">LLM mode </div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="ts-status warn">Deterministic mode</div>',
                unsafe_allow_html=True,
            )
            st.caption("Natural-language summaries are unavailable.")

        st.divider()

        st.markdown("#### Ranking")
        mode = st.selectbox(
            "Mode",
            options=list(ALL_MODES),
            index=0,
            help="mood_first: balanced. genre_first: hard-filter by favorite genres. "
                 "energy_similarity: pure feature distance.",
        )
        top_k = st.slider("Top results", min_value=3, max_value=10, value=5)
        artist_penalty = st.slider(
            "Artist diversity penalty",
            min_value=0.0, max_value=1.5, value=0.5, step=0.1,
            help="How much to demote each repeat artist. 0 disables.",
        )

        st.markdown("#### Summary style")
        style = st.radio(
            "Style",
            options=list(ALL_STYLES),
            index=0,
            horizontal=False,
            captions=[
                "Balanced explanation with citations",
                "30-word DJ pitch, second person",
                "Bullet list, third-person studio notes",
            ],
        )

        st.divider()
        st.caption(
            f"Catalog: {len(get_catalog().all_tracks)} tracks  ·  "
            f"Profiles: {len(get_profiles())}"
        )
        return {
            "mode": mode,
            "top_k": top_k,
            "artist_penalty": artist_penalty,
            "style": style,
        }


# ---------------------------------------------------------------------------
# Tab: Discover
# ---------------------------------------------------------------------------

EXAMPLE_QUERIES = [
    "calm lo-fi music for studying",
    "high energy workout playlist for running",
    "something like Daft Punk for a dinner party",
    "rainy Sunday acoustic mood",
    "moody synthwave for late-night driving",
]


def tab_discover(opts: dict[str, Any]) -> None:
    st.markdown("### Discover")
    st.caption(
        "Type a free-form mood / genre / artist request. The agent plans, "
        "retrieves from the knowledge base, scores the catalog, checks the draft, "
        "and revises once if grounding fails."
    )

    if "_pending_query" in st.session_state:
        st.session_state["query_input"] = st.session_state.pop("_pending_query")

    query = st.text_input(
        "Your request",
        placeholder="e.g. calm lo-fi music for studying",
        key="query_input",
    )

    cols = st.columns(len(EXAMPLE_QUERIES))
    for col, example in zip(cols, EXAMPLE_QUERIES):
        if col.button(example, key=f"ex_{example}", width="stretch"):
            st.session_state["_pending_query"] = example
            st.rerun()

    run = st.button("Recommend", type="primary", width="stretch")

    if not run:
        return

    if not query.strip():
        st.warning("Type a request or pick one of the examples above.")
        return

    catalog_index = {t.id: t for t in get_catalog().all_tracks}

    with st.spinner("Planning · retrieving · scoring · checking…"):
        try:
            agent = get_agent()
            response: AgentResponse = agent.recommend(
                query=query,
                mode=opts["mode"],
                artist_penalty=opts["artist_penalty"],
                style=opts["style"],
            )
        except ValueError as exc:
            st.error(str(exc))
            return

    st.session_state["last_response"] = response
    st.session_state["last_query"] = query
    _render_agent_response(response, catalog_index, opts["style"])


def _render_agent_response(
    response: AgentResponse,
    catalog_index: dict[str, Track],
    style: str,
) -> None:
    intent_label = response.intent.replace("_", " ").title()

    top = st.columns([2, 1, 1, 1])
    top[0].markdown(
        f'<div class="ts-status">Intent · {intent_label}</div>',
        unsafe_allow_html=True,
    )
    top[1].metric("Confidence", f"{response.confidence:.2f}")
    top[2].metric("Tracks", len(response.recommendations))
    top[3].metric("Style", response.style)

    if response.refused:
        st.markdown(
            '<div class="ts-refusal"><strong>Guardrail engaged.</strong> '
            "The agent refused this request before any retrieval or LLM call. "
            "Try a request about moods, genres, or artists.</div>",
            unsafe_allow_html=True,
        )
        return

    if not response.recommendations:
        st.info("No tracks matched. Try a broader mood, genre, or artist.")
        return

    st.markdown('<div class="ts-section-label">Recommendations</div>', unsafe_allow_html=True)
    render_recommendations(response.recommendations, catalog_index)

    render_summary(response.summary)
    render_style_metrics(style, response.style_metrics)
    render_citations(response.citations)
    render_confidence(response.confidence, response.passed_checks, response.checker_reasons)


# ---------------------------------------------------------------------------
# Tab: Profiles
# ---------------------------------------------------------------------------

def tab_profiles(opts: dict[str, Any]) -> None:
    st.markdown("### Saved listener profiles")
    st.caption(
        "Each profile is a structured `UserPreferences` (genres, moods, "
        "audio-feature targets, tempo range). The same scoring API runs."
    )

    profiles = get_profiles()
    catalog = get_catalog()

    cols = st.columns(len(profiles))
    for col, (key, prefs) in zip(cols, profiles.items()):
        with col:
            st.markdown(
                f"""
                <div class="ts-profile-card">
                    <div class="ts-title">{prefs.name}</div>
                    <div class="ts-artist" style="margin-top:4px;">{prefs.description}</div>
                    <div style="margin-top:10px;">
                        {''.join(f'<span class="ts-pill">{g}</span>' for g in prefs.favorite_genres)}
                    </div>
                    <div style="margin-top:6px;">
                        {''.join(f'<span class="ts-pill mood">{m}</span>' for m in prefs.favorite_moods)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Run {prefs.name}", key=f"run_profile_{key}", width="stretch"):
                st.session_state["selected_profile"] = key

    selected = st.session_state.get("selected_profile")
    if not selected:
        st.info("Pick a profile above to generate recommendations using the current sidebar settings.")
        return

    prefs = profiles[selected]
    scored = recommend_songs(
        prefs=prefs,
        songs=catalog.all_tracks,
        top_k=opts["top_k"],
        mode=opts["mode"],
        artist_penalty=opts["artist_penalty"],
    )

    st.markdown(f"#### Results for *{prefs.name}*")
    meta_cols = st.columns(4)
    meta_cols[0].metric("Mode", opts["mode"])
    meta_cols[1].metric("Style", opts["style"])
    meta_cols[2].metric("Tracks", len(scored))
    avg_score = sum(s.score for s in scored) / max(1, len(scored))
    meta_cols[3].metric("Avg score", f"{avg_score:.2f}")

    if not scored:
        st.warning("No tracks matched this profile under the current settings.")
        return

    st.markdown('<div class="ts-section-label">Recommendations</div>', unsafe_allow_html=True)
    render_scored_recommendations(scored)

    if opts["style"] != "default":
        plan = Plan(
            intent="profile",
            moods=tuple(prefs.favorite_moods),
            genres=tuple(prefs.favorite_genres),
            artists=tuple(prefs.favorite_artists),
            eras=(),
            tempo_range=prefs.tempo_range,
            target_energy=prefs.target_energy,
            target_valence=prefs.target_valence,
            target_acousticness=prefs.target_acousticness,
            success_criteria=(),
            raw_query=prefs.description,
        )
        ranked = [RankedTrack(track=s.track, score=s.score, reasons=s.reasons) for s in scored]
        styled = render_styled_fallback(opts["style"], plan, [], ranked)
        render_summary(styled)
        render_style_metrics(opts["style"], style_compliance(styled, opts["style"]))


# ---------------------------------------------------------------------------
# Tab: Catalog
# ---------------------------------------------------------------------------

def tab_catalog() -> None:
    st.markdown("### Catalog")
    st.caption("Every track the recommender can pick from. Filter by genre, mood, era, energy.")

    catalog = get_catalog()
    df = pd.DataFrame(
        [
            {
                "Title": t.title,
                "Artist": t.artist,
                "Genre": t.genre,
                "Era": t.era,
                "Year": t.release_year,
                "BPM": t.tempo_bpm,
                "Energy": t.energy,
                "Valence": t.valence,
                "Danceability": t.danceability,
                "Acousticness": t.acousticness,
                "Popularity": t.popularity,
                "Moods": ", ".join(t.moods),
            }
            for t in catalog.all_tracks
        ]
    )

    f1, f2, f3 = st.columns(3)
    genres = sorted(df["Genre"].unique())
    eras = sorted(df["Era"].unique())
    selected_genres = f1.multiselect("Genre", genres, default=[])
    selected_eras = f2.multiselect("Era", eras, default=[])
    energy_range = f3.slider("Energy range", 0.0, 1.0, (0.0, 1.0), step=0.05)

    filtered = df.copy()
    if selected_genres:
        filtered = filtered[filtered["Genre"].isin(selected_genres)]
    if selected_eras:
        filtered = filtered[filtered["Era"].isin(selected_eras)]
    filtered = filtered[
        (filtered["Energy"] >= energy_range[0]) & (filtered["Energy"] <= energy_range[1])
    ]

    summary_cols = st.columns(4)
    summary_cols[0].metric("Tracks shown", len(filtered))
    summary_cols[1].metric("Avg BPM", f"{filtered['BPM'].mean():.0f}" if len(filtered) else "—")
    summary_cols[2].metric("Avg energy", f"{filtered['Energy'].mean():.2f}" if len(filtered) else "—")
    summary_cols[3].metric("Genres", filtered["Genre"].nunique() if len(filtered) else 0)

    st.dataframe(filtered, width="stretch", height=460, hide_index=True)

    if len(filtered):
        st.markdown('<div class="ts-section-label">Genre breakdown</div>', unsafe_allow_html=True)
        breakdown = (
            filtered.groupby("Genre")
            .size()
            .reset_index(name="Tracks")
            .sort_values("Tracks", ascending=False)
        )
        max_n = int(breakdown["Tracks"].max()) or 1
        rows_html: list[str] = []
        for _, row in breakdown.iterrows():
            name = row["Genre"]
            n = int(row["Tracks"])
            pct = (n / max_n) * 100
            rows_html.append(
                f"""
                <div style="display:grid; grid-template-columns: 180px 1fr 40px; align-items:center; gap:10px; margin:6px 0;">
                    <div style="color:var(--ts-muted); font-size:0.86rem;">{name}</div>
                    <div class="ts-bar" style="height:10px;"><span style="width:{pct:.0f}%"></span></div>
                    <div style="color:var(--ts-text); font-weight:600; font-size:0.86rem; text-align:right;">{n}</div>
                </div>
                """
            )
        st.markdown("\n".join(rows_html), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab: Compare profiles
# ---------------------------------------------------------------------------

def tab_compare(opts: dict[str, Any]) -> None:
    st.markdown("### Compare profiles")
    st.caption(
        "Run all saved profiles through the same scoring API and side-by-side "
        "their top picks, average energy, and tempo. Each column is a different listener."
    )

    profiles = get_profiles()
    catalog = get_catalog()

    cols = st.columns(len(profiles))
    summary_rows: list[dict[str, Any]] = []

    for col, (key, prefs) in zip(cols, profiles.items()):
        with col:
            scored = recommend_songs(
                prefs=prefs,
                songs=catalog.all_tracks,
                top_k=opts["top_k"],
                mode=opts["mode"],
                artist_penalty=opts["artist_penalty"],
            )
            avg_energy = sum(s.track.energy for s in scored) / max(1, len(scored))
            avg_tempo = sum(s.track.tempo_bpm for s in scored) / max(1, len(scored))
            top_track = scored[0].track.title if scored else "—"
            top_genres = Counter(s.track.genre for s in scored).most_common(2)

            st.markdown(
                f"""
                <div class="ts-profile-card">
                    <div class="ts-title">{prefs.name}</div>
                    <div class="ts-artist" style="margin-top:4px;">Top pick: <strong>{top_track}</strong></div>
                    <div style="margin-top:8px;">
                        <span class="ts-pill tempo">avg BPM {avg_tempo:.0f}</span>
                        <span class="ts-pill energy">avg energy {avg_energy:.2f}</span>
                    </div>
                    <div style="margin-top:6px;">
                        {''.join(f'<span class="ts-pill">{g} · {n}</span>' for g, n in top_genres)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            for i, s in enumerate(scored, start=1):
                st.markdown(
                    f'<div style="margin-top:8px;">'
                    f'<span class="ts-rank" style="width:24px;height:24px;font-size:0.78rem;">{i}</span>'
                    f'<span style="font-weight:600;">{s.track.title}</span> '
                    f'<span style="color:var(--ts-muted);">· {s.track.artist}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            summary_rows.append({
                "Profile": prefs.name,
                "Top pick": top_track,
                "Avg BPM": round(avg_tempo, 1),
                "Avg energy": round(avg_energy, 2),
                "Genres": ", ".join(g for g, _ in top_genres),
            })

    st.markdown('<div class="ts-section-label">At a glance</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Tab: Trace
# ---------------------------------------------------------------------------

def tab_trace() -> None:
    st.markdown("### Agent trace")
    st.caption(
        "Every Plan / Retrieve / Score / Check / Revise step writes a JSON line "
        "to `logs/agent_trace.jsonl`. The most recent run is shown below."
    )

    log_path = PROJECT_ROOT / "logs" / "agent_trace.jsonl"
    if not log_path.exists():
        st.info("No trace yet. Run a query in the Discover tab first.")
        return

    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        st.error(f"Could not read trace: {exc}")
        return

    if not lines:
        st.info("Trace file is empty.")
        return

    n = st.slider("How many recent events", 5, 80, 25)
    recent = lines[-n:]

    parsed: list[dict[str, Any]] = []
    for raw in recent:
        try:
            parsed.append(json.loads(raw))
        except json.JSONDecodeError:
            continue

    if not parsed:
        st.warning("Could not parse any trace lines as JSON.")
        return

    event_types = sorted({p.get("event_type", "?") for p in parsed})
    selected_events = st.multiselect("Filter event types", event_types, default=event_types)
    filtered = [p for p in parsed if p.get("event_type") in selected_events]

    for entry in reversed(filtered):
        event = entry.get("event_type", "event")
        ts = entry.get("timestamp", "")
        with st.expander(f"{event}  ·  {ts}", expanded=False):
            st.json(entry)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def render_hero() -> None:
    st.markdown(
        """
        <div class="ts-hero">
            <h1>TuneSage</h1>
            <p>
                An agentic music recommender that turns a free-form mood, genre,
                or artist request into a short, ranked, <em>grounded</em> playlist —
                with citations, confidence, and a transparent Plan / Retrieve /
                Check / Revise loop.
            </p>
            <div>
                <span class="ts-tagchip">RAG</span>
                <span class="ts-tagchip">Agentic loop</span>
                <span class="ts-tagchip">3 ranking modes</span>
                <span class="ts-tagchip">Few-shot specialization</span>
                <span class="ts-tagchip">Guardrails</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    render_hero()
    opts = render_sidebar()

    discover, profiles, catalog, compare, trace = st.tabs(
        ["Discover", "Profiles", "Catalog", "Compare", "Trace"]
    )

    with discover:
        tab_discover(opts)
        last = st.session_state.get("last_response")
        if last and not st.session_state.get("_just_ran"):
            st.markdown('<div class="ts-section-label">Most recent run</div>', unsafe_allow_html=True)
            st.caption(f"Query: *{st.session_state.get('last_query', '')}*")

    with profiles:
        tab_profiles(opts)

    with catalog:
        tab_catalog()

    with compare:
        tab_compare(opts)

    with trace:
        tab_trace()


if __name__ == "__main__":
    main()
