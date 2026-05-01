from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _default_trace_path() -> Path:
    """Writable trace path for local dev vs serverless (Vercel/Lambda).

    Serverless runtimes are read-only except ``/tmp``; writing under ``logs/``
    raises OSError and breaks the agent mid-request.
    """
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/tunesage_agent_trace.jsonl")
    return Path("logs/agent_trace.jsonl")


def _trace_path() -> Path:
    raw = os.environ.get("TUNESAGE_TRACE_LOG", "").strip()
    if raw:
        return Path(raw)
    return _default_trace_path()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def log_trace(event_type: str, payload: dict[str, Any]) -> None:
    primary = _trace_path()
    fallbacks = [primary]
    if primary.as_posix() != "/tmp/tunesage_agent_trace.jsonl":
        fallbacks.append(Path("/tmp/tunesage_agent_trace.jsonl"))

    line = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    encoded = json.dumps(line) + "\n"
    last_err: OSError | None = None
    for path in fallbacks:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fp:
                fp.write(encoded)
            return
        except OSError as exc:
            last_err = exc
    logger.debug("trace log skipped after retries: %s", last_err)
