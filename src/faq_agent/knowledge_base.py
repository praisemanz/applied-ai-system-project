from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    chunk_id: int
    score: float
    text: str


class KnowledgeBase:
    def __init__(self, docs_path: Path) -> None:
        self.docs_path = docs_path
        self._chunks: list[RetrievedChunk] = []
        self._matrix = None
        self._vectorizer = TfidfVectorizer(stop_words="english")

    def build(self) -> None:
        texts: list[str] = []
        chunks: list[RetrievedChunk] = []
        for md_file in sorted(self.docs_path.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            for idx, chunk in enumerate(self._chunk_text(content)):
                if not chunk.strip():
                    continue
                chunks.append(
                    RetrievedChunk(
                        source=md_file.name,
                        chunk_id=idx,
                        score=0.0,
                        text=chunk.strip(),
                    )
                )
                texts.append(chunk.strip())
        if not texts:
            self._chunks = []
            self._matrix = None
            return
        self._chunks = chunks
        self._matrix = self._vectorizer.fit_transform(texts)

    def retrieve(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if not self._chunks or self._matrix is None:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix).flatten()
        ranked = scores.argsort()[::-1][:top_k]
        results: list[RetrievedChunk] = []
        for i in ranked:
            base = self._chunks[i]
            results.append(
                RetrievedChunk(
                    source=base.source,
                    chunk_id=base.chunk_id,
                    score=float(scores[i]),
                    text=base.text,
                )
            )
        return results

    @staticmethod
    def _chunk_text(text: str) -> Sequence[str]:
        text = text.replace("\r\n", "\n")
        sections = re.split(r"\n\s*\n", text)
        return [section.strip() for section in sections if section.strip()]
