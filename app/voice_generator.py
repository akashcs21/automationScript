"""JIGYASA LAB — offline narration generation.

Uses eSpeak NG (preferred on GitHub Actions Ubuntu runners) or Piper to render
the narration script to a WAV file synchronized with subtitles and scenes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import wave
from pathlib import Path

from config import NARRATION_ENGINE, NARRATION_RATE, NARRATION_VOICE, OUTPUT_DIR
from logger import logger, log_event


class VoiceError(RuntimeError):
    """Raised when narration cannot be generated."""


def _which(tool: str) -> str | None:
    return shutil.which(tool)


def generate_narration(text: str, output_wav: Path | None = None,
                       rate: int | None = None) -> Path:
    """Render ``text`` to a mono WAV file.

    Returns the path to the generated WAV. Raises VoiceError if neither eSpeak
    NG nor Piper is available, or if synthesis fails.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = output_wav or (OUTPUT_DIR / "narration.wav")
    rate = rate or NARRATION_RATE

    espeak = _which("espeak-ng") or _which("espeak")
    piper = _which("piper")

    if espeak:
        cmd = [
            espeak,
            "-v", NARRATION_VOICE,
            "-s", str(rate),
            "-w", str(out),
            text,
        ]
        logger.info("Generating narration with eSpeak NG (%d wpm, %s)", rate, NARRATION_VOICE)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise VoiceError("eSpeak NG timed out while synthesizing narration.") from exc
        if result.returncode != 0 or not out.exists():
            raise VoiceError(f"eSpeak NG failed: {result.stderr.strip()}")
        log_event("narration_generated", engine="espeak-ng", output=str(out),
                  words=len(text.split()))
        return out

    if piper:
        model = os.environ.get("PIPER_MODEL", "en_US-lessac-medium.onnx")
        cmd = [
            piper,
            "--model", model,
            "--output_file", str(out),
        ]
        logger.info("Generating narration with Piper (model %s)", model)
        try:
            proc = subprocess.run(cmd, input=text, capture_output=True,
                                  text=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise VoiceError("Piper timed out while synthesizing narration.") from exc
        if proc.returncode != 0 or not out.exists():
            raise VoiceError(f"Piper failed: {proc.stderr.strip()}")
        log_event("narration_generated", engine="piper", output=str(out),
                  words=len(text.split()))
        return out

    raise VoiceError(
        "No offline TTS engine found. Install eSpeak NG (sudo apt-get install espeak-ng) "
        "or Piper and add it to PATH."
    )


def estimate_duration(text: str, wpm: int | None = None) -> float:
    """Estimate narration duration in seconds at the configured speaking rate."""
    wpm = wpm or NARRATION_RATE
    words = len(text.split())
    return words / (wpm / 60.0)


def get_wav_duration(wav_path: Path) -> float:
    """Return the actual duration (seconds) of a WAV file using its header."""
    with wave.open(str(wav_path), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return frames / float(rate)
