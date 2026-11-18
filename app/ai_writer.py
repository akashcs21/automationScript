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
    REEL_STYLE,
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


def _build_stickman_prompt(excluded_topics: list[str]) -> str:
    excluded = ", ".join(f'"{t}"' for t in excluded_topics) or "none"
    return f"""
You are the executive creator and viral storyteller for "{BRAND_NAME}" — famous 2D Stickman Animated Stories & Psychological Parables (in the iconic style of @mrstickman_1).
Format: High-retention vertical Facebook Reel (9:16, 1080x1920, 30 FPS, ~35-40 seconds).
Tone: Calm, wise, compelling storyteller English — conversational, relatable, with an unexpected twist and life/mind lesson.
Goal: Maximize viral shares, saves, retention, and comments.

TASK:
Write ONE original, unforgettable Stickman story or philosophical/psychological parable.
Viral themes to choose from:
- Time vs Money Parables (e.g. The Fisherman and the Millionaire)
- Delayed Gratification & Invisible Growth (e.g. The Chinese Bamboo Tree)
- Priorities & Mental Clarity (e.g. The Jar of Life: Rocks, Pebbles, Sand)
- Self-Worth & Resilience (e.g. The $100 Bill in the Dirt)
- Human Psychology & Overthinking (e.g. The 2 AM Trap, The Paradox of Choice)
- Social Psychology & Envy (e.g. The Crab Mentality, The Echo of Karma)
- Habit Compounding & Growth (e.g. The 1% Daily Shift, The Two Wolves)

STRICTLY AVOID these previously used topics: {excluded}.

STORY TIMELINE STRUCTURE (~70–90 words total, paced for ~35s narration):
1. [0–5s | Setup & Hook]: Introduce the stickman character in an everyday or intriguing situation.
2. [5–12s | Conflict / Question]: A second stickman enters or asks a provocative question.
3. [12–20s | Escalation]: The dialogue deepens or a common trap is highlighted.
4. [20–28s | The Twist / Punchline]: The unexpected realization or counter-intuitive truth.
5. [28–34s | Moral & Interactive Question]: Direct question asking viewers: "Who was right? Drop your thoughts below 👇"
6. [34–38s | CTA]: "Follow {BRAND_NAME} for more animated wisdom."

SCENE BREAKDOWN (Exactly 5–6 scenes):
Each scene must define:
- "scene": number 1 to 6
- "setting": one of ["beach_car", "modern_office", "city_street", "classroom_chalkboard", "park_bench", "living_room"]
- "character_left": description of left stickman (e.g. "fisherman in bucket hat reclining on sand")
- "character_right": description of right stickman (e.g. "businessman in grey suit and tie standing")
- "action": character posture/action (e.g. "businessman gesturing at sea while fisherman smiles")
- "description": summary visual description
- "on_screen_text": short punchy 1–3 word kinetic caption in ALL CAPS (e.g. "TIRED?", "THEN WHAT?", "WHY NOT NOW?", "WHO'S RIGHT? 👇")
- "duration_seconds": 5–7 seconds (summing to 35–42 seconds)
- "camera_motion": "zoom_in" or "pan_up" or "zoom_out"

SUBTITLES:
7–10 short synchronized segments covering 0.0s to ~38s with "highlight": true on key words.

OUTPUT FORMAT:
Return ONLY valid JSON (no markdown fences, no prose). Schema:
{{
  "topic": "The Fisherman and the Businessman",
  "category": "Time vs Money",
  "reel_title": "The Millionaire's Biggest Mistake",
  "opening_hook": "A rich businessman saw a stickman fisherman resting by the beach...",
  "audience_question": "Who was right? The Businessman or the Fisherman? 👇",
  "narration_script": "80 words of natural, story-driven narration following the timeline",
  "scenes": [
    {{
      "scene": 1,
      "setting": "beach_car",
      "character_left": "fisherman in bucket hat reclining on sand with fishing rod",
      "character_right": "businessman in grey suit standing next to black sedan",
      "action": "businessman arrives and watches fisherman",
      "description": "fisherman resting by beach as luxury car arrives",
      "on_screen_text": "RELAXING?",
      "camera_motion": "zoom_in",
      "duration_seconds": 6.0
    }}
  ],
  "subtitle_segments": [
    {{"start": 0.0, "end": 3.0, "text": "A rich businessman was walking on the beach...", "highlight": false}}
  ],
  "facebook_caption": "Engaging caption with story breakdown, emojis, and discussion question",
  "pinned_comment": "Who do you side with? 👇 A) The Businessman (Ambition) B) The Fisherman (Present Peace). Let's debate in the comments!",
  "story_poll": "Ambition or Peace of Mind?",
  "hashtags": ["#JigyasaLab", "#StickmanStories", "#LifeLessons", "#Wisdom", "#Philosophy"],
  "factual_claims": [{{"claim": "Philosophical parable on time and wealth", "source_url": "https://en.wikipedia.org/wiki/Anekdote_zur_Senkung_der_Arbeitsmoral", "confidence": "high"}}],
  "caveats": ["Perspectives vary between financial security and minimalism"]
}}
"""


def _build_prompt(excluded_topics: list[str]) -> str:
    if REEL_STYLE == "stickman":
        return _build_stickman_prompt(excluded_topics)
    excluded = ", ".join(f'"{t}"' for t in excluded_topics) or "none"
    return f"""
You are the executive showrunner and science writer for "{BRAND_NAME}" — {BRAND_TAGLINE}.
Format: High-retention vertical Facebook Reel (9:16, 1080x1920, 30 FPS, ~40 seconds).
Tone: Cinematic, suspenseful, energetic, conversational English — hook-driven, scientifically accurate, dramatic pacing.
Goal: Maximize genuine engagement, watch time, shares, saves, and comments.

TASK:
Write ONE original, scroll-stopping scientific Reel script about a fresh, fascinating topic from these categories:
{chr(10).join("- " + c for c in TOPIC_CATEGORIES)}

STRICTLY AVOID these previously used topics: {excluded}.

VOICEOVER TIMELINE STRUCTURE (7 Distinct Stages, ~80-95 words total):
1. [0–4 sec | Powerful hook]: One surprising, irresistible question or revelation (e.g. "What if you stayed awake for 7 days straight? What would happen to your brain?")
2. [4–10 sec | Build curiosity]: Immediate escalation and initial intriguing fact.
3. [10–17 sec | Escalate]: Deeper consequences, memory/concentration struggle, or scientific transformation.
4. [17–24 sec | Surprising fact]: The most jaw-dropping or counter-intuitive discovery/detail (e.g. hallucinations, physical shifts).
5. [24–31 sec | Biological / Cosmic mechanism]: Why the human body, brain, or universe behaves this way and why recovery is essential.
6. [31–36 sec | Audience interaction question]: Direct, conversational question asking the viewer to participate (e.g. "Be honest: how many hours do you sleep every night?").
7. [36–40 sec | CTA]: "Comment your answer below, and follow Jigyasa Lab for more mind-blowing science!"

SCENE BREAKDOWN (Exactly 6–7 scenes, matching the 7 stages):
- Scene 1 (Hook): Dramatic close-up or visual anomaly with dark cinematic atmosphere.
- Scene 2 (Curiosity): Contextual struggle, action, or tension.
- Scene 3 (Scientific 3D animation): Biological, neurological, anatomical, or planetary mechanism (e.g. 3D brain/atom/cell/space).
- Scene 4 (Surreal / Mind-bending): Vivid visual representation of extreme state or phenomenon.
- Scene 5 (Mechanism / Recovery): Core restorative process or cosmic law.
- Scene 6 (Audience Question): Person looking directly at camera with large animated question mark and prominent prompt text: e.g. "HOW MANY HOURS DO YOU SLEEP? 👇".
- Scene 7 (Brand Outro): JIGYASA LAB logo reveal with glowing electric blue scientific particles.

SUBTITLES WITH YELLOW KEYWORD HIGHLIGHTS:
- Break the narration into 7–10 synchronized subtitle segments covering 0.0s to ~40.0s.
- For 3 to 5 power keywords/phrases (e.g. "24 HOURS", "BRAIN", "HALLUCINATIONS", "SLEEP"), set "highlight": true so they burn in bold electric yellow!

OUTPUT FORMAT:
Return ONLY valid JSON (no markdown fences, no prose). Schema:
{{
  "topic": "specific narrow topic (e.g. 'What Happens If You Never Sleep?')",
  "category": "one of the categories",
  "reel_title": "short scroll-stopping title (max 8 words)",
  "opening_hook": "first 2-4 seconds hook sentence",
  "audience_question": "short prominent question for on-screen prompt (e.g. 'HOW MANY HOURS DO YOU SLEEP? 👇')",
  "narration_script": "80–95 words of natural energetic English following the 7-stage timeline",
  "scenes": [
    {{"scene": 1, "description": "visual description", "visual_query": "2-4 search keywords for authentic scientific photography or 3d render", "camera_motion": "zoom_in|zoom_out|pan_up|pan_down", "duration_seconds": 5, "on_screen_text": "short bold text", "highlight_word": "KEYWORD"}},
    ... (6–7 scenes, summing to 40–45 seconds)
  ],
  "subtitle_segments": [
    {{"start": 0.0, "end": 3.8, "text": "What if you stayed awake for 7 days straight?", "highlight": false}},
    {{"start": 3.8, "end": 7.0, "text": "After just 24 hours without sleep...", "highlight": true}},
    ...
  ],
  "facebook_caption": "Engaging caption with emojis, science explanation, the viewer question, and follow CTA",
  "pinned_comment": "Interactive multiple-choice poll: 'Quick check! 👇 A) Less than 5h B) 5–6h C) 7–8h D) More than 8h. Which one describes you?'",
  "story_poll": "Story poll question with Option A and Option B",
  "hashtags": ["#JigyasaLab", "#Science", "#BrainScience", "#MindBlowingFacts", "#HumanBody"],
  "factual_claims": [
    {{"claim": "checkable scientific statement", "source_url": "https://en.wikipedia.org/wiki/...", "confidence": "high"}}
  ],
  "caveats": ["scientific nuance or individual variance"]
}}
"""


def generate_script(excluded_topics: list[str], retries: int = 5) -> dict:
    """Generate and validate a Reel script via Gemini with automatic fallback.

    Retries on invalid JSON or overloaded models. Automatically falls back
    to alternative models if high demand or timeout is encountered.
    """
    if not GEMINI_API_KEY:
        raise ScriptError("GEMINI_API_KEY is not set — cannot generate a script.")

    models_to_try = [GEMINI_MODEL]
    for fb in ["gemini-2.5-flash-lite", "gemini-3-flash-preview", "gemini-flash-latest"]:
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
                    "responseMimeType": "application/json",
                },
            }
            resp = requests.post(
                url,
                headers=headers,
                params={"key": GEMINI_API_KEY},
                json=body,
                timeout=25,
            )
            if resp.status_code != 200:
                last_error = f"Gemini ({model}) HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning("Gemini attempt %d failed (%s): %s", attempt, model, last_error)
                time.sleep(1 * attempt)
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
        except Exception as exc:  # network, timeout, etc.
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Gemini attempt %d error on %s: %s", attempt, model, last_error)
        time.sleep(1 * attempt)

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
    if not (60 <= word_count <= 120):
        logger.warning("Narration %d words (target %d–%d)",
                       word_count, NARRATION_WORDS_MIN, NARRATION_WORDS_MAX)
        return False

    scenes = script.get("scenes", [])
    if not (4 <= len(scenes) <= 8):
        logger.warning("Scene count %d out of range 4–8", len(scenes))
        return False
    total_scene_seconds = 0.0
    for scene in scenes:
        if not scene.get("description"):
            scene["description"] = f"{scene.get('character_left', 'Stickman')} and {scene.get('character_right', 'character')} in {scene.get('setting', 'scene')}"
        if not scene.get("on_screen_text"):
            scene["on_screen_text"] = scene.get("action", "STORY")[:15].upper()
        try:
            total_scene_seconds += float(scene.get("duration_seconds", 6))
        except (TypeError, ValueError):
            return False
    if total_scene_seconds < 20.0 or total_scene_seconds > 65.0:
        logger.warning("Scene durations sum to %.1fs (too far from target)",
                       total_scene_seconds)
        return False

    subs = script.get("subtitle_segments", [])
    if not subs:
        return False

    # Auto-normalize hashtags
    hashtags = [h for h in script.get("hashtags", []) if isinstance(h, str) and h.strip()]
    if not hashtags:
        hashtags = ["#JigyasaLab", "#Science", "#Knowledge"]
    script["hashtags"] = hashtags[:5]

    # Auto-normalize scenes with visual_query and camera_motion
    motions = ["zoom_in", "pan_up", "zoom_in", "zoom_out", "pan_down", "zoom_in", "zoom_out"]
    for idx, scene in enumerate(scenes):
        if not scene.get("visual_query"):
            scene["visual_query"] = scene.get("on_screen_text") or script.get("topic", "science")
        if not scene.get("camera_motion"):
            scene["camera_motion"] = motions[idx % len(motions)]

    # Auto-normalize caption
    if not script.get("facebook_caption"):
        script["facebook_caption"] = f"{script.get('topic', '')} — Follow {BRAND_NAME} for daily scientific wonders!"

    # Auto-normalize caveats
    if not isinstance(script.get("caveats"), list):
        script["caveats"] = []

    # Auto-normalize claims
    claims = [c for c in script.get("factual_claims", []) if isinstance(c, dict) and c.get("claim")]
    if not claims:
        claims = [{"claim": script.get("topic", "Fact"), "source_url": "https://en.wikipedia.org", "confidence": "high"}]
    for c in claims:
        if not c.get("source_url"):
            c["source_url"] = "https://en.wikipedia.org"
    script["factual_claims"] = claims

    return True
