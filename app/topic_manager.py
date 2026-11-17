"""JIGYASA LAB — topic history management.

Keeps a JSON record of previously used topics and content hashes so the system
never repeats (or near-repeats) a topic across daily runs.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, TOPICS_FILE, TOPIC_COOLDOWN_DAYS
from logger import logger, log_event


class TopicManager:
    def __init__(self, topics_file: Path = TOPICS_FILE) -> None:
        self.topics_file = topics_file
        self.topics_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if self.topics_file.exists():
            try:
                with self.topics_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "topics" in data:
                    return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read topics file (%s); starting fresh.", exc)
        return {
            "brand": "JIGYASA LAB",
            "description": "History of topics used for JIGYASA LAB daily Reels.",
            "topics": [],
            "last_updated": None,
        }

    def save(self) -> None:
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = self.topics_file.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        tmp.replace(self.topics_file)
        log_event("topics_saved", count=len(self.data.get("topics", [])))

    def content_hash(self, script: dict) -> str:
        """Stable hash of the script's factual content (title + hook + script)."""
        key = "||".join(
            str(script.get(k, "")) for k in ("topic", "reel_title", "opening_hook", "narration_script")
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def is_topic_recent(self, topic: str, days: int = TOPIC_COOLDOWN_DAYS) -> bool:
        """True if this exact topic was used within the cooldown window."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        topic_lower = topic.strip().lower()
        for entry in self.data.get("topics", []):
            if entry.get("topic", "").strip().lower() == topic_lower:
                try:
                    used_at = datetime.fromisoformat(entry.get("used_at", ""))
                except ValueError:
                    continue
                if used_at >= cutoff:
                    return True
        return False

    def is_duplicate_content(self, content_hash: str) -> bool:
        """True if a near-identical script hash was already published."""
        for entry in self.data.get("topics", []):
            if entry.get("content_hash") == content_hash:
                return True
        return False

    def record(self, topic: str, content_hash: str, status: str = "generated") -> None:
        entry = {
            "topic": topic.strip(),
            "content_hash": content_hash,
            "status": status,
            "used_at": datetime.now(timezone.utc).isoformat(),
        }
        self.data.setdefault("topics", []).append(entry)
        self.save()
        log_event("topic_recorded", topic=topic, status=status, hash=content_hash[:12])

    def is_empty(self) -> bool:
        return len(self.data.get("topics", [])) == 0
