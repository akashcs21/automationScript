"""JIGYASA LAB — subtitle generation.

Converts subtitle segments (from the AI script) into an SRT file with
timestamps synchronized to the narration and scene changes.
"""
from __future__ import annotations

from pathlib import Path

from config import OUTPUT_DIR
from logger import logger, log_event


def _format_srt_time(seconds: float) -> str:
    """HH:MM:SS,mmm for SRT."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt_text(segments: list[dict], start_index: int = 1) -> str:
    lines: list[str] = []
    index = start_index
    for seg in segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start + 2.5))
        if end <= start:
            end = start + 2.0
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        lines.append(str(index))
        lines.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
        lines.append(text)
        lines.append("")
        index += 1
    return "\n".join(lines)


def generate_srt(subtitle_segments: list[dict],
                 output_srt: Path | None = None,
                 highlight_only: bool = False) -> Path:
    """Write an SRT file from subtitle segments.

    Each segment: {start, end, text, highlight?}. When ``highlight_only`` is
    True, only segments flagged with ``highlight: true`` are written (used for
    the selective yellow-highlight subtitle track). Returns the SRT path.
    """
    output_srt = output_srt or (OUTPUT_DIR / "subtitles.srt")
    output_srt.parent.mkdir(parents=True, exist_ok=True)

    if not subtitle_segments:
        raise ValueError("No subtitle segments provided — cannot generate SRT.")

    if highlight_only:
        segments = [s for s in subtitle_segments if s.get("highlight")]
        if not segments:
            # Still emit a valid (empty-cue) file so the filter graph stays simple.
            output_srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n.\n\n", encoding="utf-8")
            log_event("subtitles_generated", highlight_only=True, segments=0,
                      output=str(output_srt))
            return output_srt
    else:
        segments = subtitle_segments

    output_srt.write_text(_segments_to_srt_text(segments), encoding="utf-8")
    log_event("subtitles_generated", highlight_only=highlight_only,
              segments=len(segments), output=str(output_srt))
    return output_srt


def split_srt(subtitle_segments: list[dict]) -> tuple[Path, Path]:
    """Write normal and highlighted SRT files. Returns (normal, highlight)."""
    normal = generate_srt(subtitle_segments, OUTPUT_DIR / "subtitles.srt")
    highlight = generate_srt(subtitle_segments, OUTPUT_DIR / "subtitles_highlight.srt",
                             highlight_only=True)
    return normal, highlight
