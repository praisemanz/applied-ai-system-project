from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    log_level: str
    top_k_kb: int
    top_k_tracks: int
    max_query_length: int


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip(),
        top_k_kb=int(os.getenv("TOP_K_KB", "3")),
        top_k_tracks=int(os.getenv("TOP_K_TRACKS", "5")),
        max_query_length=int(os.getenv("MAX_QUERY_LENGTH", "400")),
    )
