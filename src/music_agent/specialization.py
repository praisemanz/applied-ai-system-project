"""Specialization layer: few-shot exemplars and constrained-tone summary styles.

Exposes three summary styles the recommender can render in:

    - "default"      — neutral 3-5 sentence explanation (baseline behavior).
    - "dj_brief"     — second-person, <= 30 words, ends with a hook question.
    - "studio_notes" — bullet-list "engineer's notes" with feature callouts,
                       neutral third-person, <= 6 bullets, every bullet
                       cites a track or KB chunk.

The styles work in two paths:

1. Live LLM path: ``build_few_shot_prompt`` injects 2-3 curated exemplars
   (synthetic, hand-written) plus explicit rules into the chat prompt.
   This is the "few-shot" pattern from the rubric.
2. Deterministic fallback path: ``render_styled_fallback`` applies the
   same rules in code so the system measurably differs from baseline
   even without an API key.

``style_compliance`` returns the metrics that make the difference
measurable for the eval harness and tests.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Literal

from .knowledge_base import RetrievedChunk
from .planner import Plan
from .track_catalog import RankedTrack


SummaryStyle = Literal["default", "dj_brief", "studio_notes"]
ALL_STYLES: tuple[SummaryStyle, ...] = ("default", "dj_brief", "studio_notes")


@dataclass(frozen=True)
class StyleRules:
    name: SummaryStyle
    max_words: int
    require_second_person: bool
    require_bullets: bool
    forbid_first_person: bool
    must_end_with: tuple[str, ...]


_STYLE_RULES: dict[SummaryStyle, StyleRules] = {
    "default": StyleRules(
        name="default",
        max_words=120,
        require_second_person=False,
        require_bullets=False,
        forbid_first_person=False,
        must_end_with=(),
    ),
    "dj_brief": StyleRules(
        name="dj_brief",
        max_words=30,
        require_second_person=True,
        require_bullets=False,
        forbid_first_person=True,
        must_end_with=("?",),
    ),
    "studio_notes": StyleRules(
        name="studio_notes",
        max_words=90,
        require_second_person=False,
        require_bullets=True,
        forbid_first_person=True,
        must_end_with=(),
    ),
}


# Synthetic, curated exemplars. Each pair is a *target style* demo so the
# LLM can pattern-match. They reference fictitious tracks so they cannot
# be confused with real catalog content.
_FEW_SHOT_EXEMPLARS: dict[SummaryStyle, list[tuple[str, str]]] = {
    "dj_brief": [
        (
            "Late-night focus playlist; tracks: 'Soft Static' by Atrium [Ambient, 70 BPM, energy 0.2]; "
            "context: Ambient prioritizes texture over rhythm.",
            "You wanted quiet focus, so 'Soft Static' carries the room with low-energy ambient texture. Ready to lock in?",
        ),
        (
            "Cardio set; tracks: 'Pulse Run' by Volt [House, 128 BPM, energy 0.9]; "
            "context: House music drives steady high-tempo motion.",
            "You said run hard, so 'Pulse Run' locks a 128 BPM house pulse straight to your stride. Ready to go?",
        ),
    ],
    "studio_notes": [
        (
            "Romantic dinner; tracks: 'Slow Glass' by Marin [Bossa Nova, 110 BPM, energy 0.4]; "
            "context: Bossa nova blends nylon-string guitar with relaxed Brazilian rhythm.",
            "- 'Slow Glass' (Marin, Bossa Nova): 110 BPM and energy 0.4 sit in the conversation-friendly zone.\n"
            "- Bossa nova provides nylon-string guitar texture suited to dinner-table volume.\n"
            "- Tempo and acoustic-leaning timbre satisfy the romantic-mood slot.",
        ),
        (
            "Workout; tracks: 'Pulse Run' by Volt [House, 128 BPM, energy 0.9]; "
            "context: House music drives steady high-tempo motion.",
            "- 'Pulse Run' (Volt, House): 128 BPM, energy 0.9, hits the cardio target band.\n"
            "- House music sustains a steady four-on-the-floor groove for interval pacing.\n"
            "- High danceability supports the workout's high-energy slot.",
        ),
    ],
}


def get_rules(style: SummaryStyle) -> StyleRules:
    return _STYLE_RULES[style]


def build_few_shot_prompt(
    style: SummaryStyle,
    query: str,
    plan: Plan,
    kb_chunks: list[RetrievedChunk],
    ranked: list[RankedTrack],
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) seeded with style exemplars."""
    rules = _STYLE_RULES[style]
    track_block = _format_tracks(ranked)
    kb_block = _format_kb(kb_chunks)

    if style == "default":
        system_prompt = (
            "You are a grounded music recommender. "
            "Use only the supplied tracks and knowledge-base excerpts. "
            "Never invent songs, artists, or facts. "
            "Explain why the picks fit the user's request in 3-5 sentences."
        )
        user_prompt = (
            f"User request: {query}\n"
            f"Detected intent: {plan.intent}\n"
            f"Detected moods: {', '.join(plan.moods) or 'none'}\n"
            f"Detected genres: {', '.join(plan.genres) or 'none'}\n"
            f"Tracks to recommend (do not add others):\n{track_block}\n\n"
            f"Knowledge-base context:\n{kb_block}\n\n"
            "Write a concise summary that ties the picks to the request. "
            "Mention at least one detail from the knowledge base."
        )
        return system_prompt, user_prompt

    rule_lines = _rule_lines(rules)
    exemplars = _FEW_SHOT_EXEMPLARS.get(style, [])
    exemplar_block = "\n\n".join(
        f"Example input:\n{ex[0]}\n\nExample output:\n{ex[1]}" for ex in exemplars
    )

    system_prompt = (
        "You are a grounded music recommender that writes in a specific tone. "
        "Use only the supplied tracks and knowledge-base excerpts. "
        "Never invent songs, artists, or facts.\n\n"
        f"Tone rules ({rules.name}):\n{rule_lines}\n\n"
        "Pattern-match the example outputs below; do not copy their lyrics or "
        "track names — those are illustrative only.\n\n"
        f"{exemplar_block}"
    )
    user_prompt = (
        f"User request: {query}\n"
        f"Tracks to recommend (do not add others):\n{track_block}\n\n"
        f"Knowledge-base context:\n{kb_block}\n\n"
        f"Write the {rules.name} response now. Follow every tone rule."
    )
    return system_prompt, user_prompt


def render_styled_fallback(
    style: SummaryStyle,
    plan: Plan,
    kb_chunks: list[RetrievedChunk],
    ranked: list[RankedTrack],
) -> str:
    """Deterministic fallback that respects the style rules without an LLM.

    Crucially, the output measurably differs from the default fallback:
    - dj_brief is much shorter, second-person, ends with a "?"
    - studio_notes is bullet-formatted and feature-callout dense.
    """
    if not ranked:
        return "No matching tracks. Try a broader mood or genre."

    if style == "dj_brief":
        return _render_dj_brief(plan, ranked)
    if style == "studio_notes":
        return _render_studio_notes(kb_chunks, ranked)
    return _render_default(plan, kb_chunks, ranked)


def style_compliance(text: str, style: SummaryStyle) -> dict[str, object]:
    """Return a dict of metrics describing how well ``text`` follows ``style``.

    Used by tests and the eval harness so the style difference is *measurable*,
    not just claimed in prose.
    """
    rules = _STYLE_RULES[style]
    word_count = len(text.split())
    has_second_person = bool(re.search(r"\b(you|your|you're|you'll)\b", text, re.I))
    has_first_person = bool(re.search(r"\b(I|I'm|we|our|us)\b", text))
    has_bullets = any(line.lstrip().startswith(("- ", "* ", "•")) for line in text.splitlines())
    ends_well = (
        not rules.must_end_with
        or any(text.rstrip().endswith(suffix) for suffix in rules.must_end_with)
    )

    violations: list[str] = []
    if word_count > rules.max_words:
        violations.append(f"too_long ({word_count} > {rules.max_words})")
    if rules.require_second_person and not has_second_person:
        violations.append("missing_second_person")
    if rules.require_bullets and not has_bullets:
        violations.append("missing_bullets")
    if rules.forbid_first_person and has_first_person:
        violations.append("contains_first_person")
    if not ends_well:
        violations.append(f"wrong_terminator (need one of {rules.must_end_with})")

    return {
        "style": style,
        "word_count": word_count,
        "has_second_person": has_second_person,
        "has_first_person": has_first_person,
        "has_bullets": has_bullets,
        "ends_well": ends_well,
        "violations": tuple(violations),
        "compliant": len(violations) == 0,
    }


def baseline_difference(
    baseline_text: str, styled_text: str
) -> dict[str, float]:
    """Quantify how the styled output differs from the baseline output.

    Returns metrics:
        - word_count_delta: baseline - styled (positive means styled is shorter)
        - jaccard: token overlap between baseline and styled (0..1, lower = more different)
        - shared_token_ratio: |intersection| / |baseline tokens|
    """
    base_tokens = set(_tokenize(baseline_text))
    style_tokens = set(_tokenize(styled_text))
    if not base_tokens or not style_tokens:
        return {"word_count_delta": 0.0, "jaccard": 1.0, "shared_token_ratio": 1.0}
    inter = base_tokens & style_tokens
    union = base_tokens | style_tokens
    jaccard = len(inter) / len(union) if union else 1.0
    shared_token_ratio = len(inter) / len(base_tokens)
    word_count_delta = len(baseline_text.split()) - len(styled_text.split())
    return {
        "word_count_delta": float(word_count_delta),
        "jaccard": round(jaccard, 4),
        "shared_token_ratio": round(shared_token_ratio, 4),
    }


# ---------------------------------------------------------------------------
# Internal renderers
# ---------------------------------------------------------------------------

def _render_default(
    plan: Plan,
    kb_chunks: list[RetrievedChunk],
    ranked: list[RankedTrack],
) -> str:
    mood_text = ", ".join(plan.moods) if plan.moods else "your request"
    track_block = "\n".join(
        f"- {r.track.title} by {r.track.artist} "
        f"[{r.track.genre}, {r.track.tempo_bpm} BPM, energy {r.track.energy}, "
        f"valence {r.track.valence}]"
        for r in ranked
    )
    evidence_block = "\n\n".join(
        f"[{c.source}#{c.chunk_id}] {c.text}" for c in kb_chunks
    ) or "(no knowledge-base context retrieved)"
    return (
        f"For {mood_text}, the catalog suggests:\n{track_block}\n\n"
        f"Context from the knowledge base:\n{evidence_block}"
    )


def _render_dj_brief(plan: Plan, ranked: list[RankedTrack]) -> str:
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    mood_text = plan.moods[0] if plan.moods else "the vibe"
    if second is not None:
        body = (
            f"You wanted {mood_text}, so '{top.track.title}' opens at "
            f"{top.track.tempo_bpm} BPM and '{second.track.title}' keeps it locked. "
            f"Ready?"
        )
    else:
        body = (
            f"You wanted {mood_text}, so '{top.track.title}' "
            f"({top.track.genre}, {top.track.tempo_bpm} BPM) carries the set. "
            f"Ready?"
        )
    return _truncate_to_words(body, max_words=_STYLE_RULES["dj_brief"].max_words, end="?")


def _render_studio_notes(
    kb_chunks: list[RetrievedChunk],
    ranked: list[RankedTrack],
) -> str:
    """Studio-notes style: at most 3 track bullets + 1 KB bullet, <=90 words."""
    bullets: list[str] = []
    for r in ranked[:3]:
        bullets.append(
            f"- '{r.track.title}' ({r.track.artist}, {r.track.genre}): "
            f"{r.track.tempo_bpm} BPM, energy {r.track.energy}, "
            f"valence {r.track.valence}; {(r.reasons[0] if r.reasons else 'matches profile').lower()}."
        )
    if kb_chunks:
        first_chunk = kb_chunks[0]
        snippet = first_chunk.text.split(". ")[0].strip()
        if snippet:
            bullets.append(f"- KB note [{first_chunk.source}#{first_chunk.chunk_id}]: {snippet}.")
    return "\n".join(bullets)


def _format_tracks(ranked: list[RankedTrack]) -> str:
    return "\n".join(
        f"- {r.track.title} by {r.track.artist} "
        f"[{r.track.genre}, {r.track.tempo_bpm} BPM, energy {r.track.energy}, "
        f"valence {r.track.valence}]"
        for r in ranked
    )


def _format_kb(kb_chunks: list[RetrievedChunk]) -> str:
    if not kb_chunks:
        return "(no knowledge-base context retrieved)"
    return "\n\n".join(f"[{c.source}#{c.chunk_id}] {c.text}" for c in kb_chunks)


def _rule_lines(rules: StyleRules) -> str:
    lines: list[str] = [f"- Maximum {rules.max_words} words."]
    if rules.require_second_person:
        lines.append("- Address the listener directly using 'you' or 'your'.")
    if rules.forbid_first_person:
        lines.append("- Never use 'I', 'we', 'our', or 'us'.")
    if rules.require_bullets:
        lines.append("- Output must be a bullet list using '- ' at line starts.")
    if rules.must_end_with:
        terminators = " or ".join(repr(t) for t in rules.must_end_with)
        lines.append(f"- The last character must be {terminators}.")
    return "\n".join(lines)


def _truncate_to_words(text: str, max_words: int, end: str = ".") -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words]).rstrip(",.!?:; ")
    return truncated + end


def _tokenize(text: str) -> Iterable[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
