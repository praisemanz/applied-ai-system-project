from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import re
from typing import Any

from .config import Settings
from .knowledge_base import KnowledgeBase, RetrievedChunk
from .llm_client import LLMClient, Message
from .logging_utils import log_trace


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentPlan:
    intent: str
    retrieval_query: str
    success_criteria: list[str]


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    reasons: list[str]
    confidence: float


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    citations: list[str]
    confidence: float
    passed_checks: bool
    checker_reasons: list[str]


class AgenticFAQAssistant:
    def __init__(self, settings: Settings, docs_path: Path) -> None:
        self.settings = settings
        self.kb = KnowledgeBase(docs_path)
        self.kb.build()
        self.llm = LLMClient(settings.openai_api_key, settings.openai_model)

    def answer(self, question: str) -> AgentResponse:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")
        if len(question) > self.settings.max_question_length:
            raise ValueError(
                f"Question is too long ({len(question)} chars). Max is {self.settings.max_question_length}."
            )

        if self._is_disallowed_request(question):
            refusal = "I can only help with product FAQ content and safe operational guidance."
            return AgentResponse(
                answer=refusal,
                citations=[],
                confidence=0.1,
                passed_checks=True,
                checker_reasons=["refused_out_of_scope"],
            )

        plan = self._create_plan(question)
        log_trace("plan", asdict(plan))

        retrieved = self.kb.retrieve(plan.retrieval_query, self.settings.top_k_retrieval)
        retrieval_payload = [
            {
                "source": r.source,
                "chunk_id": r.chunk_id,
                "score": round(r.score, 4),
                "text_preview": r.text[:160],
            }
            for r in retrieved
        ]
        log_trace("retrieve", {"query": plan.retrieval_query, "results": retrieval_payload})

        draft_answer = self._draft_answer(question, plan, retrieved)
        log_trace("draft", {"answer_preview": draft_answer[:400]})

        check = self._check_answer(question, draft_answer, retrieved)
        log_trace("check", asdict(check))

        final_answer = draft_answer
        if not check.passed:
            final_answer = self._revise_answer(question, draft_answer, retrieved, check.reasons)
            log_trace("revise", {"reasons": check.reasons, "answer_preview": final_answer[:400]})
            check = self._check_answer(question, final_answer, retrieved)
            log_trace("recheck", asdict(check))

        citations = self._citations_from_chunks(retrieved)
        if not citations:
            citations = ["no_source_found"]

        return AgentResponse(
            answer=final_answer,
            citations=citations,
            confidence=check.confidence,
            passed_checks=check.passed,
            checker_reasons=check.reasons,
        )

    def _create_plan(self, question: str) -> AgentPlan:
        lower = question.lower()
        intent = "general_faq"
        if any(word in lower for word in ["price", "billing", "refund"]):
            intent = "billing"
        elif any(word in lower for word in ["security", "privacy", "data"]):
            intent = "security"
        elif any(word in lower for word in ["integrate", "api", "sdk", "webhook"]):
            intent = "integration"

        retrieval_query = re.sub(r"\s+", " ", lower)
        success_criteria = [
            "Answer addresses the user question directly.",
            "Answer is grounded in retrieved source text.",
            "Answer includes uncertainty when evidence is weak.",
        ]
        return AgentPlan(intent=intent, retrieval_query=retrieval_query, success_criteria=success_criteria)

    def _draft_answer(self, question: str, plan: AgentPlan, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return (
                "I could not find relevant information in the local FAQ knowledge base. "
                "Please expand the documentation in assets/*.md and try again."
            )

        evidence_block = "\n\n".join(
            f"[{c.source}#{c.chunk_id}] {c.text}" for c in chunks[: self.settings.top_k_retrieval]
        )

        if not self.llm.has_live_model:
            # Deterministic fallback keeps the app functional without external API access.
            top = chunks[0]
            return (
                f"Based on the available FAQ docs, the best answer is:\n\n{top.text}\n\n"
                f"Intent category: {plan.intent}."
            )

        system_prompt = (
            "You are a grounded product FAQ assistant. "
            "Only answer using retrieved evidence. "
            "If evidence is incomplete, say what is unknown. "
            "Keep the answer concise and practical."
        )
        user_prompt = (
            f"Question: {question}\n"
            f"Intent: {plan.intent}\n"
            f"Evidence:\n{evidence_block}\n\n"
            "Write a direct answer and mention unknowns if needed."
        )
        return self.llm.generate([Message(role="system", content=system_prompt), Message(role="user", content=user_prompt)])

    def _revise_answer(
        self,
        question: str,
        draft_answer: str,
        chunks: list[RetrievedChunk],
        reasons: list[str],
    ) -> str:
        if not chunks:
            return draft_answer
        if not self.llm.has_live_model:
            return draft_answer + "\n\nNote: confidence is limited due to weak source grounding."

        evidence_block = "\n\n".join(f"[{c.source}#{c.chunk_id}] {c.text}" for c in chunks)
        prompt = (
            "Revise the answer to fix checker issues.\n"
            f"Issues: {', '.join(reasons)}\n"
            f"Question: {question}\n"
            f"Current answer: {draft_answer}\n"
            f"Evidence:\n{evidence_block}\n\n"
            "Return a corrected grounded answer."
        )
        return self.llm.generate([Message(role="user", content=prompt)], temperature=0.1)

    def _check_answer(self, question: str, answer: str, chunks: list[RetrievedChunk]) -> CheckResult:
        reasons: list[str] = []
        if not answer.strip():
            reasons.append("empty_answer")

        q_terms = {t for t in re.findall(r"[a-zA-Z]{4,}", question.lower())}
        answer_terms = {t for t in re.findall(r"[a-zA-Z]{4,}", answer.lower())}
        coverage = len(q_terms.intersection(answer_terms)) / max(1, len(q_terms))
        if coverage < 0.2:
            reasons.append("low_question_coverage")

        evidence_text = " ".join(c.text.lower() for c in chunks)
        grounded_hits = sum(1 for term in answer_terms if term in evidence_text)
        grounding_ratio = grounded_hits / max(1, len(answer_terms))
        if chunks and grounding_ratio < 0.2:
            reasons.append("weak_grounding")
        if not chunks:
            reasons.append("no_retrieval_context")

        confidence = max(0.05, min(0.98, (coverage * 0.45) + (grounding_ratio * 0.55)))
        passed = len(reasons) == 0
        return CheckResult(passed=passed, reasons=reasons, confidence=round(confidence, 2))

    @staticmethod
    def _citations_from_chunks(chunks: list[RetrievedChunk]) -> list[str]:
        citations = [f"{c.source}#{c.chunk_id}" for c in chunks]
        seen: set[str] = set()
        unique: list[str] = []
        for citation in citations:
            if citation not in seen:
                seen.add(citation)
                unique.append(citation)
        return unique

    @staticmethod
    def _is_disallowed_request(question: str) -> bool:
        lower = question.lower()
        return any(
            blocked in lower
            for blocked in ["exploit", "malware", "hate", "violence", "terror", "sexual"]
        )
