from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import re
from typing import Any

from .config import Settings
from .knowledge_base import KnowledgeBase, RetrievedChunk
from .llm_client import LLMClient, Message
from .logging_utils import log_trace
from .planner import Plan, build_plan
from .scoring import RankingMode, UserPreferences, recommend_songs
from .track_catalog import RankedTrack, Track, TrackCatalog, TrackQuery


logger = logging.getLogger(__name__)


DISALLOWED_TERMS: tuple[str, ...] = (
    "exploit", "malware", "hack", "crack", "pirate", "torrent",
    "hate", "violence", "terror", "sexual",
)


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    reasons: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class Recommendation:
    track_id: str
    title: str
    artist: str
    genre: str
    score: float
    why: str


@dataclass(frozen=True)
class AgentResponse:
    summary: str
    recommendations: list[Recommendation]
    citations: list[str]
    confidence: float
    passed_checks: bool
    checker_reasons: list[str]
    intent: str
    refused: bool = False


class MusicRecommenderAgent:
    def __init__(self, settings: Settings, docs_path: Path, catalog_path: Path) -> None:
        self.settings = settings
        self.kb = KnowledgeBase(docs_path)
        self.kb.build()
        self.catalog = TrackCatalog.from_json(catalog_path)
        self.llm = LLMClient(settings.openai_api_key, settings.openai_model)

    def recommend(
        self,
        query: str,
        mode: RankingMode = "mood_first",
        artist_penalty: float = 0.5,
    ) -> AgentResponse:
        query = query.strip()
        if not query:
            raise ValueError("Query cannot be empty.")
        if len(query) > self.settings.max_query_length:
            raise ValueError(
                f"Query is too long ({len(query)} chars). Max is {self.settings.max_query_length}."
            )

        if self._is_disallowed_request(query):
            log_trace("guardrail", {"query": query, "reason": "disallowed_terms"})
            return AgentResponse(
                summary="I can only recommend music from the local catalog and explain it with the curated knowledge base.",
                recommendations=[],
                citations=[],
                confidence=0.1,
                passed_checks=True,
                checker_reasons=["refused_out_of_scope"],
                intent="refusal",
                refused=True,
            )

        plan = build_plan(query, self.catalog)
        log_trace("plan", _plan_payload(plan))

        kb_chunks = self.kb.retrieve(self._kb_query(plan), self.settings.top_k_kb)
        log_trace("kb_retrieve", {
            "query": self._kb_query(plan),
            "results": [_chunk_preview(c) for c in kb_chunks],
        })

        ranked = self._rank_with_mode(plan, mode=mode, artist_penalty=artist_penalty)
        log_trace("catalog_search", {
            "mode": mode,
            "artist_penalty": artist_penalty,
            "ranked": [_ranked_payload(r) for r in ranked],
        })

        if not ranked:
            ranked, plan = self._broaden_and_retry(plan, mode, artist_penalty)

        summary = self._draft_summary(query, plan, kb_chunks, ranked)
        log_trace("draft", {"summary_preview": summary[:400]})

        recommendations = [self._to_recommendation(r) for r in ranked]
        check = self._check(plan, ranked, summary, kb_chunks)
        log_trace("check", asdict(check))

        if not check.passed and ranked:
            summary = self._revise_summary(query, plan, kb_chunks, ranked, check.reasons)
            log_trace("revise", {"summary_preview": summary[:400], "reasons": list(check.reasons)})
            check = self._check(plan, ranked, summary, kb_chunks)
            log_trace("recheck", asdict(check))

        citations = self._build_citations(kb_chunks, ranked)

        return AgentResponse(
            summary=summary,
            recommendations=recommendations,
            citations=citations,
            confidence=check.confidence,
            passed_checks=check.passed,
            checker_reasons=list(check.reasons),
            intent=plan.intent,
        )

    def _rank_with_mode(
        self,
        plan: Plan,
        mode: RankingMode,
        artist_penalty: float,
    ) -> list[RankedTrack]:
        prefs = UserPreferences(
            name="from_query",
            description=plan.raw_query,
            favorite_genres=plan.genres,
            favorite_moods=plan.moods,
            favorite_artists=plan.artists,
            target_energy=plan.target_energy,
            target_valence=plan.target_valence,
            target_acousticness=plan.target_acousticness,
            tempo_range=plan.tempo_range,
        )
        scored = recommend_songs(
            prefs=prefs,
            songs=self.catalog.all_tracks,
            top_k=self.settings.top_k_tracks,
            mode=mode,
            artist_penalty=artist_penalty,
        )
        return [RankedTrack(track=s.track, score=s.score, reasons=s.reasons) for s in scored]

    def _broaden_and_retry(
        self,
        plan: Plan,
        mode: RankingMode,
        artist_penalty: float,
    ) -> tuple[list[RankedTrack], Plan]:
        log_trace("revise_filters", {"action": "broadened_query"})
        broadened = Plan(
            intent=plan.intent,
            moods=plan.moods,
            genres=(),
            artists=plan.artists,
            eras=(),
            tempo_range=None,
            target_energy=plan.target_energy,
            target_valence=plan.target_valence,
            target_acousticness=plan.target_acousticness,
            success_criteria=plan.success_criteria,
            raw_query=plan.raw_query,
        )
        results = self._rank_with_mode(broadened, mode, artist_penalty)
        return results, broadened

    def _kb_query(self, plan: Plan) -> str:
        parts: list[str] = []
        parts.extend(plan.moods)
        parts.extend(plan.genres)
        parts.extend(plan.artists)
        if not parts:
            parts.append(plan.raw_query)
        return " ".join(parts)

    def _draft_summary(
        self,
        query: str,
        plan: Plan,
        kb_chunks: list[RetrievedChunk],
        ranked: list[RankedTrack],
    ) -> str:
        if not ranked:
            return (
                "I could not find tracks in the catalog that match this request. "
                "Try a broader mood (focus, party, romantic) or a specific genre or artist."
            )

        evidence_block = "\n\n".join(
            f"[{c.source}#{c.chunk_id}] {c.text}" for c in kb_chunks
        ) or "(no knowledge-base context retrieved)"

        track_block = "\n".join(
            f"- {r.track.title} by {r.track.artist} "
            f"[{r.track.genre}, {r.track.tempo_bpm} BPM, energy {r.track.energy}, "
            f"valence {r.track.valence}]"
            for r in ranked
        )

        if not self.llm.has_live_model:
            mood_text = ", ".join(plan.moods) if plan.moods else "your request"
            return (
                f"For {mood_text}, the catalog suggests:\n{track_block}\n\n"
                f"Context from the knowledge base:\n{evidence_block}"
            )

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
            f"Knowledge-base context:\n{evidence_block}\n\n"
            "Write a concise summary that ties the picks to the request. "
            "Mention at least one detail from the knowledge base."
        )
        return self.llm.generate(
            [Message(role="system", content=system_prompt), Message(role="user", content=user_prompt)]
        )

    def _revise_summary(
        self,
        query: str,
        plan: Plan,
        kb_chunks: list[RetrievedChunk],
        ranked: list[RankedTrack],
        reasons: tuple[str, ...],
    ) -> str:
        if not self.llm.has_live_model:
            mood_text = ", ".join(plan.moods) if plan.moods else "your request"
            track_lines = "\n".join(
                f"- {r.track.title} by {r.track.artist} ({r.track.genre})" for r in ranked
            )
            kb_lines = "\n".join(c.text.split(". ")[0] + "." for c in kb_chunks[:2]) or ""
            return (
                f"Recommendations for {mood_text}:\n{track_lines}\n\n"
                f"Why these fit: {kb_lines}"
            )

        evidence_block = "\n\n".join(
            f"[{c.source}#{c.chunk_id}] {c.text}" for c in kb_chunks
        ) or "(no knowledge-base context retrieved)"
        track_block = "\n".join(
            f"- {r.track.title} by {r.track.artist} ({r.track.genre})" for r in ranked
        )
        prompt = (
            "Revise the summary to fix checker issues.\n"
            f"Issues: {', '.join(reasons)}\n"
            f"Original request: {query}\n"
            f"Allowed tracks:\n{track_block}\n"
            f"Knowledge-base context:\n{evidence_block}\n\n"
            "Return a corrected summary that explicitly mentions each track and "
            "ties it to the user's request using the knowledge base. "
            "Do not invent tracks not on the list."
        )
        return self.llm.generate([Message(role="user", content=prompt)], temperature=0.1)

    def _check(
        self,
        plan: Plan,
        ranked: list[RankedTrack],
        summary: str,
        kb_chunks: list[RetrievedChunk],
    ) -> CheckResult:
        reasons: list[str] = []

        if not summary.strip():
            reasons.append("empty_summary")

        if not ranked:
            reasons.append("no_recommendations")
            return CheckResult(passed=False, reasons=tuple(reasons), confidence=0.1)

        # Title-grounding: every track listed in the summary should be one we ranked.
        catalog_titles_lower = {t.title.lower() for t in self.catalog.all_tracks}
        ranked_titles_lower = {r.track.title.lower() for r in ranked}

        # Pull quoted-style track names that the LLM may have invented.
        candidate_titles = re.findall(r'"([^"\n]{2,40})"', summary)
        invented = [
            t for t in candidate_titles
            if t.lower() not in ranked_titles_lower
            and t.lower() in catalog_titles_lower  # heuristic: real titles only
        ]
        if invented:
            reasons.append("recommended_unranked_tracks")

        # Each ranked track should appear by title in the summary.
        missing = [r.track.title for r in ranked if r.track.title.lower() not in summary.lower()]
        if missing:
            reasons.append("missing_track_mentions")

        # KB grounding: the summary should reference at least one KB term when KB chunks exist.
        if kb_chunks:
            kb_terms = set()
            for c in kb_chunks:
                kb_terms.update(re.findall(r"[a-zA-Z]{5,}", c.text.lower()))
            summary_terms = set(re.findall(r"[a-zA-Z]{5,}", summary.lower()))
            kb_overlap = len(kb_terms & summary_terms)
            if kb_overlap < 2:
                reasons.append("weak_kb_grounding")

        # Mood / genre satisfaction in the ranked set.
        if plan.moods:
            satisfied = any(
                set(m.lower() for m in r.track.moods) & set(plan.moods)
                for r in ranked
            )
            if not satisfied:
                reasons.append("mood_not_represented")

        if plan.genres:
            satisfied = any(
                r.track.genre.lower() in {g.lower() for g in plan.genres}
                for r in ranked
            )
            if not satisfied:
                reasons.append("genre_not_represented")

        # Confidence: blend of average rank score and check pass rate.
        avg_score = sum(r.score for r in ranked) / max(1, len(ranked))
        normalized = min(1.0, avg_score / 6.0)
        penalty = 0.15 * len(reasons)
        confidence = max(0.1, min(0.98, normalized - penalty))

        passed = len(reasons) == 0
        return CheckResult(passed=passed, reasons=tuple(reasons), confidence=round(confidence, 2))

    def _to_recommendation(self, ranked: RankedTrack) -> Recommendation:
        why = "; ".join(ranked.reasons) if ranked.reasons else "matches request profile"
        return Recommendation(
            track_id=ranked.track.id,
            title=ranked.track.title,
            artist=ranked.track.artist,
            genre=ranked.track.genre,
            score=round(ranked.score, 3),
            why=why,
        )

    @staticmethod
    def _build_citations(kb_chunks: list[RetrievedChunk], ranked: list[RankedTrack]) -> list[str]:
        citations: list[str] = []
        seen: set[str] = set()
        for c in kb_chunks:
            tag = f"{c.source}#{c.chunk_id}"
            if tag not in seen:
                seen.add(tag)
                citations.append(tag)
        for r in ranked:
            tag = f"catalog:{r.track.id}"
            if tag not in seen:
                seen.add(tag)
                citations.append(tag)
        return citations

    @staticmethod
    def _is_disallowed_request(query: str) -> bool:
        lowered = query.lower()
        return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in DISALLOWED_TERMS)


def _plan_payload(plan: Plan) -> dict[str, Any]:
    return {
        "intent": plan.intent,
        "moods": list(plan.moods),
        "genres": list(plan.genres),
        "artists": list(plan.artists),
        "eras": list(plan.eras),
        "tempo_range": list(plan.tempo_range) if plan.tempo_range else None,
        "target_energy": plan.target_energy,
        "target_valence": plan.target_valence,
        "target_acousticness": plan.target_acousticness,
        "success_criteria": list(plan.success_criteria),
    }


def _track_query_payload(query: TrackQuery) -> dict[str, Any]:
    return {
        "moods": list(query.moods),
        "genres": list(query.genres),
        "artists": list(query.artists),
        "eras": list(query.eras),
        "tempo_range": list(query.tempo_range) if query.tempo_range else None,
        "target_energy": query.target_energy,
        "target_valence": query.target_valence,
        "target_acousticness": query.target_acousticness,
    }


def _ranked_payload(ranked: RankedTrack) -> dict[str, Any]:
    return {
        "id": ranked.track.id,
        "title": ranked.track.title,
        "artist": ranked.track.artist,
        "genre": ranked.track.genre,
        "score": round(ranked.score, 3),
        "reasons": list(ranked.reasons),
    }


def _chunk_preview(chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "source": chunk.source,
        "chunk_id": chunk.chunk_id,
        "score": round(chunk.score, 4),
        "text_preview": chunk.text[:160],
    }
