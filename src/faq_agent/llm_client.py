from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from openai import OpenAI


@dataclass(frozen=True)
class Message:
    role: str
    content: str


class LLMClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = OpenAI(api_key=api_key) if api_key else None

    @property
    def has_live_model(self) -> bool:
        return self._client is not None

    def generate(self, messages: Iterable[Message], temperature: float = 0.2) -> str:
        if not self._client:
            raise RuntimeError("OPENAI_API_KEY is missing. Add it to your environment to run live generation.")
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
