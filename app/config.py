"""JIGYASA LAB — runtime configuration.

Reads environment variables (or a local .env via python-dotenv when present)
and exposes brand, API, rendering and publishing settings as constants.
Secrets are never printed to logs.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # pragma: no cover - optional local dev convenience
    from dotenv import load_dotenv  # type: ignore

    # Load a local .env if present (never committed). GitHub Actions supplies
    # secrets directly as environment variables, so this is a no-op there.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
except Exception:  # dotenv not installed or unreadable — fine in CI
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets"
MUSIC_DIR = BASE_DIR / "music"
SOUNDS_DIR = BASE_DIR / "sounds"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
TOPICS_FILE = DATA_DIR / "topics.json"
PUBLISHED_FILE = DATA_DIR / "published.json"

# Brand
BRAND_NAME = os.getenv("BRAND_NAME", "JIGYASA LAB")
BRAND_TAGLINE = "Explore Everything. Question Everything."
LANGUAGE = "en"
AUDIENCE = "Global"

# Reel constraints
DURATION_MIN = 35
DURATION_MAX = 45
TARGET_DURATION = 40
WIDTH = 1080
HEIGHT = 1920
FPS = 30
ASPECT_RATIO = "9:16"
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
PIXEL_FORMAT = "yuv420p"

# Palette (dark navy, black, electric blue, subtle gold)
COLOR_NAVY = "#0A1128"
COLOR_BLACK = "#05070A"
COLOR_ELECTRIC_BLUE = "#00D4FF"
COLOR_GOLD = "#C5A059"
COLOR_WHITE = "#FFFFFF"
COLOR_YELLOW = "#FFD166"

# Word target for ~35-45s narration at ~2.0-2.3 words/sec
NARRATION_WORDS_MIN = 75
NARRATION_WORDS_MAX = 100

# AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
GEMINI_MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "2048"))

# Meta Graph API
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v27.0")

# Publishing controls
PUBLISH_ENABLED = os.getenv("PUBLISH_ENABLED", "false").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Narration
NARRATION_ENGINE = os.getenv("NARRATION_ENGINE", "espeak")  # espeak or piper
NARRATION_VOICE = os.getenv("NARRATION_VOICE", "en")
NARRATION_RATE = int(os.getenv("NARRATION_RATE", "175"))

# Limits
MAX_REELS_PER_RUN = 1
TOPIC_COOLDOWN_DAYS = 30

# Graph API base
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def validate_config() -> list[str]:
    """Return a list of human-readable configuration problems (empty = OK)."""
    problems: list[str] = []
    if not GEMINI_API_KEY:
        problems.append("GEMINI_API_KEY is not set — AI script generation cannot run.")
    if not FB_PAGE_ID:
        problems.append("FB_PAGE_ID is not set — Facebook publishing cannot run.")
    if not FB_PAGE_ACCESS_TOKEN:
        problems.append("FB_PAGE_ACCESS_TOKEN is not set — Facebook publishing cannot run.")
    return problems


def is_publishing_allowed() -> bool:
    """True only when publishing is explicitly enabled AND not in dry run."""
    return PUBLISH_ENABLED and not DRY_RUN
