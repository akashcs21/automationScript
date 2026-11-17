"""JIGYASA LAB — structured logging.

Writes timestamped logs to stdout (captured by GitHub Actions) and an optional
run log file under output/. Secret values are never logged.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))
LOG_FILE = OUTPUT_DIR / "run.log"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the project logger."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("jigyasa_lab")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # File logging is best-effort; stdout is the primary sink.
        pass

    return logger


logger = setup_logging()


def log_event(event: str, **kwargs: Any) -> None:
    """Emit a structured JSON log event (safe for log aggregation)."""
    payload: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    payload.update(kwargs)
    logger.info(json.dumps(payload, ensure_ascii=False))


def redact(value: str | None) -> str:
    """Return a redacted representation of a secret/token for logging."""
    if not value:
        return "<unset>"
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}…{value[-4:]} ({len(value)} chars)"
