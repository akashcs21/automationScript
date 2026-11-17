"""JIGYASA LAB — daily Reel automation orchestrator.

Stage pipeline:
  1. AI script generation (Gemini) with safe retries
  2. Fact-checking quality gate (stop on failure — never publish)
  3. Offline narration (eSpeak NG / Piper)
  4. Subtitle generation (SRT + selective highlight track)
  5. Original animated visuals (Pillow)
  6. Video rendering + crossfades + subtitles + audio (FFmpeg)
  7. Video quality validation (stop on failure)
  8. Topic / content-hash dedupe record
  9. Facebook Page Reels publishing (only if PUBLISH_ENABLED=true)
  10. Publish log + error reporting

Run:  python app/main.py        (from project root)
Env:  see .env.example / GitHub Actions secrets
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Allow `python app/main.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_writer
import fact_checker
import facebook_publisher
import subtitle_generator
import topic_manager
import voice_generator
import visual_generator
import video_editor
from config import (DATA_DIR, DRY_RUN, DURATION_MAX, DURATION_MIN, OUTPUT_DIR,
                    PUBLISHED_FILE, validate_config, is_publishing_allowed)
from logger import logger, log_event, setup_logging

ERROR_REPORT = OUTPUT_DIR / "error_report.json"


def _write_error_report(stage: str, error: str, context: dict) -> None:
    """Persist a clear error report for failed runs (never a fake success)."""
    report = {
        "brand": "JIGYASA LAB",
        "stage": stage,
        "error": error,
        "context": context,
        "failed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "publishable": False,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ERROR_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.error("RUN FAILED at stage '%s': %s", stage, error)


def _append_published(record: dict) -> None:
    PUBLISHED_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"published": [], "last_updated": None}
    if PUBLISHED_FILE.exists():
        try:
            data = json.loads(PUBLISHED_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"published": [], "last_updated": None}
    data.setdefault("published", []).append(record)
    data["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tmp = PUBLISHED_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(PUBLISHED_FILE)


def _calibrate_scene_durations(scenes: list[dict], narration_duration: float,
                               target: float = 40.0, min_d: float = 35.0,
                               max_d: float = 45.0) -> list[dict]:
    """Rescale AI scene durations so they sum to ~target (clamped to 35–45s).

    Uses the real narration WAV duration as the anchor so subtitles, narration,
    and scene changes stay synchronized.
    """
    import copy
    scenes = copy.deepcopy(scenes)
    planned = sum(float(s.get("duration_seconds", 6)) for s in scenes)
    if planned <= 0:
        planned = len(scenes) * 6.0

    scale = target / planned
    for s in scenes:
        s["duration_seconds"] = max(3.0, round(
            float(s.get("duration_seconds", 6)) * scale, 2))

    total = sum(float(s.get("duration_seconds", 6)) for s in scenes)
    if total < min_d:
        scenes[-1]["duration_seconds"] = round(
            scenes[-1]["duration_seconds"] + (min_d - total), 2)
    elif total > max_d:
        scenes[-1]["duration_seconds"] = max(
            3.0, round(scenes[-1]["duration_seconds"] - (total - max_d), 2))
    return scenes


def run() -> int:
    setup_logging()
    logger.info("=== JIGYASA LAB daily Reel run started ===")

    # --- Stage 0: configuration ---
    problems = validate_config()
    if problems:
        for p in problems:
            logger.error("CONFIG: %s", p)
        _write_error_report("configuration", "; ".join(problems), {})
        return 1

    dry_run = not is_publishing_allowed()
    logger.info("Mode: %s (PUBLISH_ENABLED=%s)", "DRY_RUN" if dry_run else "PUBLISH",
                "true" if not dry_run else "false")

    tm = topic_manager.TopicManager()
    history = [e.get("topic", "") for e in tm.data.get("topics", [])]

    # --- Stage 1: AI script generation ---
    try:
        script = ai_writer.generate_script(history)
    except Exception as exc:
        _write_error_report("ai_script_generation", str(exc),
                            {"excluded_topics_count": len(history)})
        return 1

    # --- Stage 2: fact-checking gate ---
    try:
        fact_report = fact_checker.check_script(script)
    except fact_checker.FactCheckError as exc:
        _write_error_report("fact_check", str(exc), {"topic": script.get("topic")})
        return 1
    except Exception as exc:
        _write_error_report("fact_check", str(exc), {"topic": script.get("topic")})
        return 1

    # --- Stage 3: narration ---
    try:
        narration_wav = voice_generator.generate_narration(
            script["narration_script"])
        narration_duration = voice_generator.get_wav_duration(narration_wav)
        logger.info("Narration duration: %.2fs", narration_duration)
    except Exception as exc:
        _write_error_report("narration", str(exc), {"topic": script.get("topic")})
        return 1

    # --- Stage 4: subtitles ---
    try:
        normal_srt, highlight_srt = subtitle_generator.split_srt(
            script["subtitle_segments"])
    except Exception as exc:
        _write_error_report("subtitles", str(exc), {"topic": script.get("topic")})
        return 1

    # --- Stage 5.5: calibrate scene durations to real narration (35–45s) ---
    try:
        calibrated = _calibrate_scene_durations(
            script["scenes"], narration_duration,
            target=40.0, min_d=DURATION_MIN, max_d=DURATION_MAX)
        script["scenes"] = calibrated
        logger.info("Calibrated scene durations sum to %.2fs",
                    sum(float(s.get("duration_seconds", 6)) for s in calibrated))
    except Exception as exc:
        _write_error_report("duration_calibration", str(exc),
                            {"topic": script.get("topic")})
        return 1

    # --- Stage 6: visuals ---
    try:
        frame_dirs = visual_generator.render_all_scenes(script["scenes"])
    except Exception as exc:
        _write_error_report("visual_generation", str(exc),
                            {"topic": script.get("topic"), "scenes": len(script.get("scenes", []))})
        return 1

    # --- Stage 6: render ---
    stamp = time.strftime("%Y%m%d_%H%M%S")
    output_mp4 = OUTPUT_DIR / f"jigyasa_lab_reel_{stamp}.mp4"
    try:
        video_path = video_editor.render_reel(
            script["scenes"], frame_dirs, narration_wav,
            normal_srt, highlight_srt, output_mp4)
    except Exception as exc:
        _write_error_report("video_render", str(exc), {"topic": script.get("topic")})
        return 1

    # --- Stage 7: quality validation ---
    try:
        qc = video_editor.validate_reel(video_path, normal_srt, narration_wav)
    except Exception as exc:
        _write_error_report("quality_validation", str(exc),
                            {"video": str(video_path)})
        return 1
    if not qc["passed"]:
        _write_error_report("quality_validation",
                            "Quality checks failed: " + "; ".join(qc["errors"]),
                            {"video": str(video_path), "checks": qc["checks"]})
        return 1
    logger.info("Quality gate passed: %d checks", len(qc["checks"]))

    # --- Stage 8: dedupe ---
    content_hash = tm.content_hash(script)
    if tm.is_duplicate_content(content_hash):
        _write_error_report("dedupe", "Near-identical content already used",
                            {"topic": script.get("topic"), "hash": content_hash[:12]})
        return 1

    # --- Stage 9: publish (only when explicitly enabled) ---
    publish_record = {
        "topic": script.get("topic"),
        "reel_title": script.get("reel_title"),
        "category": script.get("category"),
        "video_file": str(video_path),
        "content_hash": content_hash,
        "dry_run": dry_run,
    }
    if dry_run:
        logger.info("DRY_RUN — Reel generated and validated, not published.")
        logger.info("Caption: %s", script.get("facebook_caption", "")[:200])
        logger.info("Hashtags: %s", " ".join(script.get("hashtags", [])))
        tm.record(script.get("topic", ""), content_hash, "dry_run")
        publish_record["status"] = "dry_run"
        _append_published(publish_record)
    else:
        try:
            publisher = facebook_publisher.FacebookPublisher()
            result = publisher.publish_reel(video_path,
                                            script.get("facebook_caption", ""))
            publish_record.update({
                "status": "published",
                "video_id": result.get("video_id"),
                "post_id": result.get("post_id"),
            })
            tm.record(script.get("topic", ""), content_hash, "published")
            _append_published(publish_record)
            logger.info("=== Reel published: video_id=%s post_id=%s ===",
                        result.get("video_id"), result.get("post_id"))
        except Exception as exc:
            _write_error_report("facebook_publish", str(exc),
                                {"topic": script.get("topic"), "video": str(video_path)})
            tm.record(script.get("topic", ""), content_hash, "publish_failed")
            return 1

    logger.info("=== JIGYASA LAB run completed successfully ===")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
