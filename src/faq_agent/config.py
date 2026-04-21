from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    log_level: str
    top_k_retrieval: int
    max_question_length: int



def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip(),
        top_k_retrieval=int(os.getenv("TOP_K_RETRIEVAL", "4")),
        max_question_length=int(os.getenv("MAX_QUESTION_LENGTH", "800")),
    )
