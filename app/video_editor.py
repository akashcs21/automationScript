"""JIGYASA LAB — video rendering & quality validation.

Assembles Pillow frame sequences into a vertical MP4 Reel (1080x1920, 30 FPS,
H.264/AAC), adds crossfade scene transitions, burns professional subtitles,
mixes narration with original procedural background music and sound effects,
then runs quality checks before publishing.
"""
from __future__ import annotations

import json
import math
import random
import subprocess
from pathlib import Path

from config import (
    AUDIO_CODEC, DURATION_MAX, DURATION_MIN, FPS, HEIGHT, OUTPUT_DIR,
    PIXEL_FORMAT, VIDEO_CODEC, WIDTH,
)
from logger import logger, log_event

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# Meta Reels safety ceiling (well under the 4 GB absolute upload limit).
MAX_FILE_SIZE_BYTES = 900 * 1024 * 1024

PLACEHOLDER_TOKENS = ("lorem ipsum", "placeholder", "todo", "tbd", "xxx",
                      "scene description", "[insert", "{your")


class VideoError(RuntimeError):
    """Raised when rendering or quality validation fails."""


def _require_tools() -> None:
    for tool in (FFMPEG, FFPROBE):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            raise VideoError(f"{tool} is not installed — video rendering cannot run.")


def _probe(path: Path) -> dict:
    cmd = [FFPROBE, "-v", "error", "-print_format", "json",
           "-show_streams", "-show_format", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise VideoError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _format_duration(info: dict) -> float:
    for s in info.get("streams", []):
        if s.get("codec_type") == "video" and s.get("duration"):
            return float(s["duration"])
    return float(info.get("format", {}).get("duration", 0))


def _resolution(info: dict) -> tuple[int, int]:
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            return int(s.get("width", 0)), int(s.get("height", 0))
    return 0, 0


def _has_audio_stream(info: dict) -> bool:
    return any(s.get("codec_type") == "audio" for s in info.get("streams", []))


def _get_scale_crop() -> str:
    """Scale & crop filter guaranteeing exactly 1080x1920."""
    return (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},format={PIXEL_FORMAT}")


def _generate_background_music(duration: float, output_wav: Path) -> None:
    """Procedural ambient pad — no copyrighted material. Calm cinematic drone."""
    rate = 44100
    samples = int(rate * duration)
    freqs = [65.41, 98.00, 130.81, 196.00]  # low ambient chord
    pcm = bytearray()
    for i in range(samples):
        ti = i / rate
        swell = 0.5 + 0.5 * math.sin(2 * math.pi * ti / max(duration, 1))
        sample = sum(0.12 * math.sin(2 * math.pi * f * ti) for f in freqs)
        trem = 0.95 + 0.05 * math.sin(2 * math.pi * 3.5 * ti)
        val = int(max(-1.0, min(1.0, sample * swell * trem * 0.5)) * 32767)
        pcm += val.to_bytes(2, "little", signed=True)

    raw = output_wav.with_suffix(".raw")
    raw.write_bytes(pcm)
    subprocess.run(
        [FFMPEG, "-y", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", str(raw),
         str(output_wav)],
        capture_output=True, check=True, timeout=60)
    raw.unlink(missing_ok=True)
    if not output_wav.exists():
        raise VideoError("Failed to encode background music.")


def _write_wav_simple(path: Path, rate: int, samples: list[int]) -> None:
    with path.open("wb") as f:
        f.write(b"RIFF")
        f.write((36 + len(samples) * 2).to_bytes(4, "little"))
        f.write(b"WAVEfmt ")
        f.write((16).to_bytes(4, "little"))
        f.write((1).to_bytes(2, "little"))  # PCM
        f.write((1).to_bytes(2, "little"))  # mono
        f.write(rate.to_bytes(4, "little"))
        f.write((rate * 2).to_bytes(4, "little"))
        f.write((2).to_bytes(2, "little"))
        f.write((16).to_bytes(2, "little"))
        f.write(b"data")
        f.write((len(samples) * 2).to_bytes(4, "little"))
        for v in samples:
            f.write(max(-32768, min(32767, v)).to_bytes(2, "little", signed=True))


def _generate_sfx(output_dir: Path) -> dict[str, Path]:
    """Original sound effects: soft chime + subtle whoosh (procedural)."""
    rate = 44100
    sfx: dict[str, Path] = {}

    chime = [int(0.45 * math.exp(-i / rate * 4) *
               (math.sin(2 * math.pi * 880 * i / rate) +
                0.5 * math.sin(2 * math.pi * 1320 * i / rate)) * 32767)
             for i in range(int(rate * 0.9))]
    _write_wav_simple(output_dir / "sfx_chime.wav", rate, chime)
    sfx["chime"] = output_dir / "sfx_chime.wav"

    rng = random.Random(7)
    whoosh = []
    for i in range(int(rate * 0.5)):
        ti = i / rate
        env = math.exp(-(ti - 0.15) ** 2 / 0.02) * 0.4
        whoosh.append(int(env * rng.uniform(-1, 1) * 18000))
    _write_wav_simple(output_dir / "sfx_whoosh.wav", rate, whoosh)
    sfx["whoosh"] = output_dir / "sfx_whoosh.wav"

    log_event("sfx_generated", count=len(sfx), output=str(output_dir))
    return sfx


def _fit_duration(video_path: Path, min_d: float = DURATION_MIN,
                  max_d: float = DURATION_MAX, target_d: float = 40.0) -> Path:
    """Guarantee the final MP4 lands within 35–45s using FFmpeg.

    - If longer than max_d: trim to max_d (fast copy, no re-encode).
    - If shorter than min_d: append a freeze-frame of the last frame until min_d.
    Returns the (possibly replaced) video path.
    """
    dur = _format_duration(_probe(video_path))
    if min_d <= dur <= max_d:
        return video_path

    tmp = video_path.with_suffix(".fit.mp4")
    if dur > max_d:
        # Trim to max_d without re-encoding where possible.
        cmd = [
            FFMPEG, "-y", "-i", str(video_path),
            "-c", "copy", "-t", str(max_d),
            "-movflags", "+faststart", str(tmp),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode != 0 or not tmp.exists():
            raise VideoError(f"Duration trim failed: {res.stderr.strip()[-500:]}")
        log_event("duration_fitted", action="trimmed",
                  from_seconds=round(dur, 2), to_seconds=max_d)
    else:
        # Pad with a freeze-frame of the last frame to reach min_d.
        pad = min_d - dur
        freeze = OUTPUT_DIR / "freeze_last.mp4"
        cmd_freeze = [
            FFMPEG, "-y", "-i", str(video_path),
            "-vf", f"freeze=end=1",
            "-frames:v", "1",
            "-c:v", VIDEO_CODEC, "-pix_fmt", PIXEL_FORMAT,
            "-t", str(pad), "-an", str(freeze),
        ]
        res = subprocess.run(cmd_freeze, capture_output=True, text=True, timeout=300)
        if res.returncode != 0 or not freeze.exists():
            raise VideoError(f"Freeze-frame pad failed: {res.stderr.strip()[-500:]}")

        # Concat original + freeze.
        list_file = OUTPUT_DIR / "concat_list.txt"
        list_file.write_text(
            f"file '{video_path.as_posix()}'\n"
            f"file '{freeze.as_posix()}'\n",
            encoding="utf-8",
        )
        cmd_cat = [
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-t", str(min_d),
            "-movflags", "+faststart", str(tmp),
        ]
        res = subprocess.run(cmd_cat, capture_output=True, text=True, timeout=300)
        if res.returncode != 0 or not tmp.exists():
            raise VideoError(f"Duration pad concat failed: {res.stderr.strip()[-500:]}")
        freeze.unlink(missing_ok=True)
        list_file.unlink(missing_ok=True)
        log_event("duration_fitted", action="padded",
                  from_seconds=round(dur, 2), to_seconds=min_d)

    tmp.replace(video_path)
    return video_path


def _encode_scene(scene_index: int, frame_dir: Path, duration: float,
                  output_mp4: Path) -> None:
    """Encode one scene's frame sequence into a silent MP4 with fade-out."""
    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", str(frame_dir / "frame_%04d.png"),
        "-vf", f"fade=t=out:st={max(0.0, duration - 1.0)}:d=1,{_get_scale_crop()}",
        "-c:v", VIDEO_CODEC, "-pix_fmt", PIXEL_FORMAT,
        "-r", str(FPS), "-t", str(duration),
        "-an", str(output_mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if res.returncode != 0 or not output_mp4.exists():
        raise VideoError(f"Scene {scene_index} encode failed: {res.stderr.strip()[-800:]}")


def _build_filtergraph(scene_videos: list[Path], subtitles_srt: Path,
                       highlight_srt: Path | None, total_duration: float) -> str:
    """FFmpeg filtergraph: crossfade scenes + subtitles + audio mix."""
    parts: list[str] = []
    trans_dur = 1.0
    cumulative = 0.0
    prev_label = None

    for idx, sv in enumerate(scene_videos):
        dur = _format_duration(_probe(sv))
        if idx == 0:
            parts.append(
                f"[0:v]fade=t=in:st=0:d=1,{_get_scale_crop()}[v{idx}]"
            )
            prev_label = f"[v{idx}]"
            cumulative = dur
            continue
        offset = max(0.1, cumulative - trans_dur)
        parts.append(
            f"{prev_label}[{idx}:v]xfade=transition=fade:duration={trans_dur}"
            f":offset={offset},{_get_scale_crop()}[v{idx}]"
        )
        prev_label = f"[v{idx}]"
        cumulative += dur

    final_video = prev_label or "[0:v]"

    # Burn subtitles (normal + optional highlighted track).
    normal_style = ("force_style='FontName=DejaVu Sans-Bold,FontSize=28,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "BackColour=&H60000000,Outline=2,Shadow=1,MarginV=90,"
                    "Alignment=2'")
    vf = f"{final_video},subtitles='{subtitles_srt.as_posix()}':{normal_style}"
    if highlight_srt and highlight_srt.exists():
        hl_style = ("force_style='FontName=DejaVu Sans-Bold,FontSize=30,"
                    "PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,"
                    "BackColour=&H60000000,Outline=2,Shadow=1,MarginV=90,"
                    "Alignment=2'")
        vf += f",subtitles='{highlight_srt.as_posix()}':{hl_style}"
    parts.append(f"{vf}[outv]")

    # Audio: narration + looped music + SFX at scene starts.
    n_idx = len(scene_videos)
    m_idx = n_idx + 1
    a_parts: list[str] = [
        f"[{n_idx}:a]volume=1.0[a_nar]",
        f"[{m_idx}:a]aloop=loop=-1:size=2e+09,volume=0.16[a_mus]",
        "[a_nar][a_mus]amix=inputs=2:duration=longest[a_mix]",
    ]

    sfx_idx = m_idx + 1
    sfx_labels: list[str] = []
    scene_durs = [_format_duration(_probe(sv)) for sv in scene_videos]
    cum = 0.0
    si = 0
    for d in scene_durs:
        sfx_key = "chime" if si % 2 == 0 else "whoosh"
        label = f"[{sfx_idx + si}:a]volume=0.7,adelay={int(cum * 1000)}|{int(cum * 1000)}[sfx{si}]"
        a_parts.append(label)
        sfx_labels.append(f"[sfx{si}]")
        cum += d
        si += 1

    if sfx_labels:
        a_parts.append(f"[a_mix]{''.join(sfx_labels)}amix=inputs={len(sfx_labels) + 1}"
                       f":duration=longest[a_final]")
        final_audio = "[a_final]"
    else:
        final_audio = "[a_mix]"

    return "; ".join(parts + a_parts), "[outv]", final_audio


def render_reel(scenes: list[dict], frame_dirs: list[Path],
                narration_wav: Path, subtitles_srt: Path,
                highlight_srt: Path | None, output_mp4: Path) -> Path:
    """Render the final MP4 Reel. Returns the output path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _require_tools()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    scene_videos: list[Path] = []
    for i, (scene, sdir) in enumerate(zip(scenes, frame_dirs)):
        duration = float(scene.get("duration_seconds", 6))
        scene_v = OUTPUT_DIR / f"scene_{i:02d}.mp4"
        _encode_scene(i, sdir, duration, scene_v)
        scene_videos.append(scene_v)
        log_event("scene_encoded", scene=i, duration=duration,
                  output=str(scene_v))

    total_duration = sum(_format_duration(_probe(sv)) for sv in scene_videos)

    music_wav = OUTPUT_DIR / "bg_music.wav"
    _generate_background_music(total_duration + 5, music_wav)
    sfx = _generate_sfx(OUTPUT_DIR)

    filter_complex, video_label, audio_label = _build_filtergraph(
        scene_videos, subtitles_srt, highlight_srt, total_duration
    )

    input_args: list[str] = []
    for sv in scene_videos:
        input_args += ["-i", str(sv)]
    input_args += ["-i", str(narration_wav), "-i", str(music_wav)]
    input_args += ["-i", str(sfx["chime"]), "-i", str(sfx["whoosh"])]

    cmd = [
        FFMPEG, "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", video_label, "-map", audio_label,
        "-c:v", VIDEO_CODEC, "-pix_fmt", PIXEL_FORMAT, "-r", str(FPS),
        "-c:a", AUDIO_CODEC, "-b:a", "128k",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(output_mp4),
    ]
    logger.info("Rendering final Reel (%d scenes, ~%.1fs) ...",
                len(scene_videos), total_duration)
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0 or not output_mp4.exists():
        raise VideoError(f"Final render failed: {res.stderr.strip()[-1500:]}")

    # Safety net: guarantee 35–45s even if AI/Fmpeg drifted.
    output_mp4 = _fit_duration(output_mp4)

    log_event("reel_rendered", output=str(output_mp4),
              size_bytes=output_mp4.stat().st_size,
              duration_seconds=round(_format_duration(_probe(output_mp4)), 2))
    return output_mp4


def validate_reel(video_path: Path, subtitles_srt: Path,
                  narration_wav: Path) -> dict:
    """Quality gate for the rendered Reel. Raises VideoError on failure."""
    report: dict = {"passed": True, "checks": [], "errors": []}

    def check(name: str, ok: bool, detail: str = "") -> None:
        report["checks"].append({"name": name, "passed": bool(ok), "detail": detail})
        if not ok:
            report["passed"] = False
            report["errors"].append(f"{name}: {detail}")

    if not video_path.exists():
        raise VideoError(f"Rendered video missing: {video_path}")

    info = _probe(video_path)
    width, height = _resolution(info)
    duration = _format_duration(info)
    size = video_path.stat().st_size

    check("container_mp4", video_path.suffix.lower() == ".mp4", video_path.suffix)
    check("resolution_1080x1920", (width, height) == (WIDTH, HEIGHT),
          f"{width}x{height}")
    check("duration_35_45s", DURATION_MIN <= duration <= DURATION_MAX,
          f"{duration:.2f}s")
    check("has_audio_stream", _has_audio_stream(info))
    check("file_size_limit", size < MAX_FILE_SIZE_BYTES,
          f"{size / 1024 / 1024:.1f} MB")

    try:
        decode = subprocess.run(
            [FFMPEG, "-v", "error", "-i", str(video_path), "-f", "null", "-"],
            capture_output=True, text=True, timeout=300)
        check("decodable_by_ffmpeg", decode.returncode == 0,
              decode.stderr.strip()[:200] if decode.returncode else "ok")
    except Exception as exc:
        check("decodable_by_ffmpeg", False, str(exc))

    check("video_stream_present",
          any(s.get("codec_type") == "video" for s in info.get("streams", [])))

    subs_text = subtitles_srt.read_text(encoding="utf-8") if subtitles_srt.exists() else ""
    check("subtitles_present", subtitles_srt.exists() and bool(subs_text.strip()))
    check("subtitles_have_content",
          bool(re.search(r"\d{2}:\d{2}:\d{2},\d{3} -->", subs_text)))
    low_subs = subs_text.lower()
    check("no_placeholder_text",
          not any(tok in low_subs for tok in PLACEHOLDER_TOKENS))

    check("narration_present", narration_wav.exists()
          and narration_wav.stat().st_size > 1000)

    log_event("quality_check", passed=report["passed"], checks=report["checks"],
              errors=report["errors"])
    return report
