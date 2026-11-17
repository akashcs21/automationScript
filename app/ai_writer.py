"""JIGYASA LAB — AI script generation via Gemini.

Calls the Gemini REST API directly with ``requests`` (free-tier model) and
returns a *validated* structured JSON script. Invalid/incomplete responses are
retried safely; an invalid or incomplete script is never published.
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import Any

import requests

from config import (
    BRAND_NAME,
    BRAND_TAGLINE,
    DURATION_MAX,
    DURATION_MIN,
    GEMINI_API_KEY,
    GEMINI_MAX_TOKENS,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    LANGUAGE,
    NARRATION_WORDS_MAX,
    NARRATION_WORDS_MIN,
)
from logger import logger, log_event

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class ScriptError(RuntimeError):
    """Raised when script generation or validation fails."""


# Topics the system may draw from (used only as inspiration; Gemini chooses one).
TOPIC_CATEGORIES = [
    "Space and astronomy",
    "Science and physics",
    "Human body and psychology",
    "Technology and AI",
    "History and archaeology",
    "Ocean and wildlife",
    "Mysteries and unusual discoveries",
]


def _build_prompt(excluded_topics: list[str]) -> str:
    excluded = ", ".join(f'"{t}"' for t in excluded_topics) or "none"
    return f"""
You are the head writer for "{BRAND_NAME}" — {BRAND_TAGLINE}.
Audience: Global ({LANGUAGE}). Reel duration: 35–45 seconds (vertical 9:16).
Brand tone: cinematic, curious, scientific, honest — no clickbait, no hype.

TASK: Write ONE original daily Reel script about a fresh topic from these categories:
{chr(10).join("- " + c for c in TOPIC_CATEGORIES)}

STRICTLY AVOID these previously used topics: {excluded}.
Do not repeat or near-repeat any of them. Pick a genuinely different fact.

OUTPUT: Return ONLY valid JSON (no markdown fences, no prose). Keys exactly:
{{
  "topic": "specific narrow topic (e.g. 'Why Venus rotates backward')",
  "category": "one of the categories above",
  "reel_title": "short scroll-stopping title (max 8 words)",
  "opening_hook": "first 2 seconds — one surprising sentence, max 18 words",
  "narration_script": "75–100 words of natural spoken English, hook to strong ending",
  "scenes": [
    {{"scene": 1, "description": "visual description for animated scene", "duration_seconds": 5, "on_screen_text": "short bold text"}},
    ... (5–7 scenes, durations sum to 35–45s)
  ],
  "subtitle_segments": [
    {{"start": 0.0, "end": 2.5, "text": "subtitle text", "highlight": false}},
    ... (timestamps cover the full narration, synced to scenes)
  ],
  "facebook_caption": "engaging caption ending with a subtle follow CTA",
  "hashtags": ["#JigyasaLab", "#Science", "..."] (3–5 tags),
  "factual_claims": [
    {{"claim": "checkable factual statement", "source_url": "https://credible.source/...", "confidence": "high"}}
  ],
  "caveats": ["any scientific uncertainty or 'scientists believe' phrasing needed"]
}}

RULES:
- Hook within the first 2 seconds.
- Narration approx {NARRATION_WORDS_MIN}–{NARRATION_WORDS_MAX} words.
- No fabricated scientific facts. No misleading clickbait.
- Natural spoken English. Strong ending + subtle follow CTA.
- Every factual claim needs a real, credible source URL (NASA, ESA, peer-reviewed journals, universities, museums, reputable science publications).
- Distinguish established evidence from hypothetical scenarios in caveats.
- Scene descriptions must be original, animatable motion-graphics briefs (space backgrounds, planets, particles, diagrams, light effects).
- If you cannot verify a claim, mark confidence "low" or omit the claim — do not fabricate.
"""


def generate_script(excluded_topics: list[str], retries: int = 3) -> dict:
    """Generate and validate a Reel script via Gemini.

    Retries on invalid JSON or incomplete schema. Raises ScriptError if no
    usable script is produced after retries.
    """
    if not GEMINI_API_KEY:
        raise ScriptError("GEMINI_API_KEY is not set — cannot generate a script.")

    models_to_try = [GEMINI_MODEL]
    for fb in ["gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
        if fb not in models_to_try:
            models_to_try.append(fb)

    headers = {"Content-Type": "application/json"}
    prompt = _build_prompt(excluded_topics)

    last_error: str | None = None
    for attempt in range(1, retries + 1):
        model = models_to_try[(attempt - 1) % len(models_to_try)]
        url = GEMINI_URL.format(model=model)
        try:
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": GEMINI_TEMPERATURE,
                    "maxOutputTokens": GEMINI_MAX_TOKENS,
                },
            }
            resp = requests.post(
                url,
                headers=headers,
                params={"key": GEMINI_API_KEY},
                json=body,
                timeout=60,
            )
            if resp.status_code != 200:
                last_error = f"Gemini ({model}) HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning("Gemini attempt %d failed: %s", attempt, last_error)
                time.sleep(2 * attempt)
                continue

            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            script = _parse_json_text(text)

            if _validate_script(script):
                log_event("script_generated", topic=script.get("topic"),
                          words=len(script.get("narration_script", "").split()),
                          scenes=len(script.get("scenes", [])))
                return script

            last_error = "script failed schema validation"
            logger.warning("Gemini attempt %d: %s", attempt, last_error)
        except ScriptError as exc:
            last_error = str(exc)
            logger.warning("Gemini attempt %d raised: %s", attempt, last_error)
        except Exception as exc:  # network, parse, etc.
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Gemini attempt %d error: %s", attempt, last_error)
        time.sleep(2 * attempt)

    raise ScriptError(f"Failed to generate a valid script after {retries} attempts: {last_error}")


def _parse_json_text(text: str) -> dict:
    text = text.strip()
    # Strip accidental markdown fences.
    if text.startswith("```"):
        text = text.split("```", 2)
        text = text[1] if len(text) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to salvage the largest {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise ScriptError(f"Gemini returned invalid JSON: {text[:300]}")


def _validate_script(script: dict) -> bool:
    if not isinstance(script, dict):
        return False

    required = ["topic", "reel_title", "opening_hook", "narration_script",
                "scenes", "subtitle_segments", "facebook_caption", "hashtags",
                "factual_claims", "caveats"]
    for key in required:
        if key not in script or script[key] in (None, ""):
            logger.warning("Script missing required key: %s", key)
            return False

    narration = script.get("narration_script", "")
    word_count = len(narration.split())
    if not (NARRATION_WORDS_MIN <= word_count <= NARRATION_WORDS_MAX + 15):
        logger.warning("Narration %d words (target %d–%d)",
                       word_count, NARRATION_WORDS_MIN, NARRATION_WORDS_MAX)
        return False

    # Narration at ~2.2 words/sec should land inside 35–45s.
    est_narration_secs = word_count / 2.2
    if not (DURATION_MIN - 3 <= est_narration_secs <= DURATION_MAX + 3):
        logger.warning("Estimated narration %.1fs outside 35–45s window",
                       est_narration_secs)
        return False

    scenes = script.get("scenes", [])
    if not (5 <= len(scenes) <= 7):
        logger.warning("Scene count %d out of range 5–7", len(scenes))
        return False
    total_scene_seconds = 0.0
    for scene in scenes:
        if not scene.get("description") or not scene.get("on_screen_text"):
            return False
        try:
            total_scene_seconds += float(scene.get("duration_seconds", 6))
        except (TypeError, ValueError):
            return False
    if not (DURATION_MIN <= total_scene_seconds <= DURATION_MAX):
        logger.warning("Scene durations sum to %.1fs (must be 35–45s)",
                       total_scene_seconds)
        return False

    subs = script.get("subtitle_segments", [])
    if not subs:
        return False

    hashtags = script.get("hashtags", [])
    if not (3 <= len(hashtags) <= 5):
        return False

    claims = script.get("factual_claims", [])
    for claim in claims:
        if not claim.get("claim") or not claim.get("source_url"):
            return False

    if not script.get("facebook_caption"):
        return False

    return True
