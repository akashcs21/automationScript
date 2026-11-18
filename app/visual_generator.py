"""JIGYASA LAB — original animated visual generation with Pillow.

Generates frame sequences for each scene: space backgrounds, rotating planets,
stars and nebulae, moving particles, scientific diagrams, light effects and
animated typography. Outputs PNG frames that FFmpeg later assembles into the
Reel. No stock footage or downloaded media is used.
"""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from config import (
    ASSETS_DIR,
    COLOR_BLACK,
    COLOR_ELECTRIC_BLUE,
    COLOR_GOLD,
    COLOR_NAVY,
    COLOR_WHITE,
    COLOR_YELLOW,
    FPS,
    HEIGHT,
    OUTPUT_DIR,
    WIDTH,
)
from logger import logger, log_event

FRAMES_DIR = OUTPUT_DIR / "frames"
FONT_BOLD = ASSETS_DIR / "font_bold.ttf"
FONT_REGULAR = ASSETS_DIR / "font_regular.ttf"

# Deterministic but varied seed per run so every Reel looks unique.
random.seed(int(os.environ.get("JIGYASA_SEED", "42")))


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    candidates = [path] if path.exists() else []
    # Fallbacks for GitHub-hosted Ubuntu runners.
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for cand in candidates:
        if Path(cand).exists():
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _new_space_background(frame_index: int, total_frames: int) -> Image.Image:
    """Dark navy/black space with a subtle moving nebula and distant stars."""
    img = Image.new("RGB", (WIDTH, HEIGHT), _hex_to_rgb(COLOR_BLACK))
    draw = ImageDraw.Draw(img)

    # Deep navy gradient toward the top.
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(10 * (1 - t) + 0 * t)
        g = int(17 * (1 - t) + 4 * t)
        b = int(40 * (1 - t) + 10 * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Nebula blobs (slow pulse).
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * frame_index / total_frames)
    neb = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ndraw = ImageDraw.Draw(neb)
    cx = WIDTH * (0.35 + 0.15 * pulse)
    cy = HEIGHT * (0.4 + 0.1 * math.sin(frame_index / 20))
    radius = 260 + 60 * pulse
    ndraw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(0, 40, 90, int(18 + 10 * pulse)),
    )
    neb = neb.filter(ImageFilter.GaussianBlur(radius=90))
    img = Image.alpha_composite(img.convert("RGBA"), neb).convert("RGB")

    # Distant starfield.
    star_draw = ImageDraw.Draw(img)
    star_count = 320
    rng = random.Random(1001)
    for _ in range(star_count):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, HEIGHT - 1)
        twinkle = 0.4 + 0.6 * abs(math.sin((frame_index + x * 7 + y * 13) / 23))
        bright = int(200 * twinkle)
        size = 1 if twinkle > 0.7 else 0
        star_draw.rectangle([x, y, x + size, y + size], fill=(bright, bright, bright + 10))

    return img


def _draw_planet(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int,
                 frame_index: int, total_frames: int, ring: bool = False) -> None:
    """A shaded, rotating planet with a subtle terminator."""
    base = _hex_to_rgb(COLOR_ELECTRIC_BLUE)
    rot = (frame_index / total_frames) * 2 * math.pi * 1.5

    # Planet disc with shading.
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            if x * x + y * y > radius * radius:
                continue
            px, py = cx + x, cy + y
            if not (0 <= px < WIDTH and 0 <= py < HEIGHT):
                continue
            # Latitude shading.
            lat = y / radius
            light = 0.55 + 0.45 * lat
            # Rotation swirl.
            swirl = 0.08 * math.sin((x + y) * 0.07 + rot)
            r = min(255, int(base[0] * light * (1 + swirl)))
            g = min(255, int(base[1] * light * (1 + swirl)))
            b = min(255, int(base[2] * light * (1 + swirl)))
            draw.point((px, py), fill=(r, g, b))

    # Highlight rim.
    highlight = 25
    hx = cx - int(radius * 0.35 * math.cos(rot))
    hy = cy - int(radius * 0.35 * math.sin(rot))
    draw.ellipse([hx - highlight, hy - highlight, hx + highlight, hy + highlight],
                 fill=(255, 255, 255))

    if ring:
        draw.ellipse(
            [cx - radius * 1.6, cy - radius * 0.45, cx + radius * 1.6, cy + radius * 0.45],
            outline=(*_hex_to_rgb(COLOR_GOLD), 220),
            width=6,
        )


def _draw_particles(draw: ImageDraw.ImageDraw, frame_index: int,
                    count: int = 45) -> None:
    """Moving dust/particle motes in the foreground."""
    rng = random.Random(2024 + frame_index // 5)
    for i in range(count):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, HEIGHT - 1)
        drift = (frame_index * (i % 5 + 1)) % WIDTH
        px = (x + drift) % WIDTH
        py = (y + (frame_index * 2) % HEIGHT) % HEIGHT
        bright = int(120 + 135 * abs(math.sin(frame_index / 10 + i)))
        size = 1 if i % 3 == 0 else 0
        draw.rectangle([px, py, px + size, py + size],
                       fill=(bright, bright, bright))


def _draw_light_flare(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                      frame_index: int) -> None:
    """Subtle electric-blue light flare."""
    pulse = int(60 + 40 * math.sin(frame_index / 6))
    for radius in (40, 20, 8):
        alpha = max(0, pulse - radius * 2)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(0, 212, 255),
        )


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if font.getlength(trial) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw_typography(draw: ImageDraw.ImageDraw, text: str, center: tuple[int, int],
                     frame_index: int, total_frames: int, highlight_word: str | None = None,
                     max_width: int | None = None) -> None:
    """Bold white on-screen text with optional selective yellow highlighting."""
    max_width = max_width or int(WIDTH * 0.88)
    font_size = 64
    font = _font(font_size, bold=True)
    lines = _wrap_text(text, font, max_width)
    # Shrink if too tall.
    line_h = font.size
    while len(lines) * line_h > HEIGHT * 0.55 and font_size > 32:
        font_size -= 4
        font = _font(font_size, bold=True)
        line_h = font.size
        lines = _wrap_text(text, font, max_width)

    cx, cy = center
    total_h = len(lines) * line_h
    start_y = cy - total_h // 2 + line_h // 4
    fade = min(1.0, frame_index / (total_frames * 0.25))  # fade-in

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        x = cx - font.getlength(line) // 2
        alpha = int(255 * fade)
        if highlight_word and highlight_word in line:
            parts = line.split(highlight_word)
            x_cursor = x
            for j, part in enumerate(parts):
                if part:
                    draw.text((x_cursor, y), part, font=font,
                              fill=(255, 255, 255))
                    x_cursor += font.getlength(part)
                if j < len(parts) - 1:
                    draw.text((x_cursor, y), highlight_word, font=font,
                              fill=_hex_to_rgb(COLOR_YELLOW))
                    x_cursor += font.getlength(highlight_word)
        else:
            draw.text((x, y), line, font=font, fill=(255, 255, 255))


def _draw_diagram_orbit(draw: ImageDraw.ImageDraw, center: tuple[int, int],
                        frame_index: int) -> None:
    """Simple animated orbital diagram (planet around star)."""
    cx, cy = center
    angle = (frame_index / 30) * 2 * math.pi
    radius = 150
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                 outline=(30, 60, 100), width=2)
    px = int(cx + radius * math.cos(angle))
    py = int(cy + radius * math.sin(angle))
    draw.ellipse([px - 9, py - 9, px + 9, py + 9], fill=_hex_to_rgb(COLOR_ELECTRIC_BLUE))
    draw.line([(cx, cy), (px, py)], fill=(60, 120, 180), width=2)
    draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=_hex_to_rgb(COLOR_GOLD))


def _draw_diagram_atom(draw: ImageDraw.ImageDraw, center: tuple[int, int],
                       frame_index: int) -> None:
    """Animated atom diagram (nucleus + orbiting electrons)."""
    cx, cy = center
    draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=_hex_to_rgb(COLOR_GOLD))
    for offset, speed in ((0, 1.0), (2.1, 0.7), (4.2, 0.5)):
        angle = (frame_index / 18) * speed + offset
        radius = 52 + offset * 14
        px = int(cx + radius * math.cos(angle))
        py = int(cy + radius * math.sin(angle))
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     outline=(40, 80, 130), width=1)
        draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=_hex_to_rgb(COLOR_ELECTRIC_BLUE))


def _draw_diagram_brain(draw: ImageDraw.ImageDraw, center: tuple[int, int],
                        frame_index: int) -> None:
    """Animated neural network / brain synaptic pulses."""
    cx, cy = center
    nodes = [
        (-80, -60), (-40, -90), (0, -100), (40, -90), (80, -60),
        (-100, -20), (-50, -30), (0, -40), (50, -30), (100, -20),
        (-90, 30), (-40, 20), (0, 10), (40, 20), (90, 30),
        (-60, 80), (-20, 70), (20, 70), (60, 80)
    ]
    for i, (x1, y1) in enumerate(nodes):
        for j, (x2, y2) in enumerate(nodes[i + 1:], i + 1):
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 85:
                pulse = 0.5 + 0.5 * math.sin(frame_index / 8 + i * 0.7)
                alpha_val = int(40 + 80 * pulse)
                draw.line([(cx + x1, cy + y1), (cx + x2, cy + y2)],
                          fill=(alpha_val // 2, alpha_val, int(alpha_val * 1.5)), width=2)
    for i, (nx, ny) in enumerate(nodes):
        firing = math.sin(frame_index / 6 + i * 1.2) > 0.4
        color = _hex_to_rgb(COLOR_YELLOW) if firing else _hex_to_rgb(COLOR_ELECTRIC_BLUE)
        r = 8 if firing else 5
        draw.ellipse([cx + nx - r, cy + ny - r, cx + nx + r, cy + ny + r], fill=color)


def _draw_question_badge(draw: ImageDraw.ImageDraw, center: tuple[int, int],
                         frame_index: int) -> None:
    """Prominent animated interaction card with pulsing question prompt."""
    cx, cy = center
    pulse = 1.0 + 0.05 * math.sin(frame_index / 5)
    bw, bh = int(340 * pulse), int(90 * pulse)
    draw.rounded_rectangle([cx - bw, cy - bh, cx + bw, cy + bh], radius=24,
                           fill=(10, 25, 55), outline=_hex_to_rgb(COLOR_ELECTRIC_BLUE), width=3)
    q_font = _font(int(46 * pulse), bold=True)
    draw.text((cx, cy), "❓ COMMENT YOUR ANSWER 👇", font=q_font, anchor="mm",
              fill=_hex_to_rgb(COLOR_YELLOW))


def _draw_brand_reveal(draw: ImageDraw.ImageDraw, center: tuple[int, int],
                       frame_index: int) -> None:
    """Scientific particle burst with JIGYASA LAB brand reveal."""
    cx, cy = center
    pulse = 0.5 + 0.5 * math.sin(frame_index / 8)
    r = int(140 + 20 * pulse)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=_hex_to_rgb(COLOR_ELECTRIC_BLUE), width=3)
    inner_r = int(r * 0.8)
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                 outline=_hex_to_rgb(COLOR_GOLD), width=1)
    b_font = _font(54, bold=True)
    draw.text((cx, cy - 25), "JIGYASA LAB", font=b_font, anchor="mm", fill=(255, 255, 255))
    s_font = _font(28, bold=False)
    draw.text((cx, cy + 35), "EXPLORE • QUESTION", font=s_font, anchor="mm",
              fill=_hex_to_rgb(COLOR_ELECTRIC_BLUE))


def _fetch_scientific_visual(query: str, theme: str) -> Image.Image | None:
    """Fetch high-resolution scientific or space imagery from Wikimedia Commons or Pexels."""
    import urllib.parse
    from io import BytesIO
    import requests

    pexels_key = os.environ.get("PEXELS_API_KEY")
    if pexels_key:
        try:
            p_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=3"
            p_resp = requests.get(p_url, headers={"Authorization": pexels_key}, timeout=8)
            if p_resp.status_code == 200:
                photos = p_resp.json().get("photos", [])
                if photos:
                    img_url = photos[0].get("src", {}).get("large2x") or photos[0].get("src", {}).get("original")
                    if img_url:
                        dl = requests.get(img_url, timeout=12)
                        if dl.status_code == 200:
                            return Image.open(BytesIO(dl.content)).convert("RGB")
        except Exception as exc:
            logger.debug("Pexels fetch failed: %s", exc)

    candidates = [query]
    if theme == "brain":
        candidates += ["human brain neural synapse", "neuroscience brain scan", "neuron activity microscopic"]
    elif theme == "space" or any(w in query.lower() for w in ("planet", "space", "star", "galaxy", "mars")):
        candidates += ["hubble space telescope nebula", "deep space galaxy", "astronomy cosmic"]
    elif theme == "atom":
        candidates += ["quantum physics atom", "magnetic field physics simulation"]
    elif theme == "body":
        candidates += ["human biology cell", "microscopic biology organism"]
    elif theme == "question":
        candidates += ["human curious thinking portrait", "deep thinking science"]

    headers = {"User-Agent": "JigyasaLabReels/2.0 (contact@jigyasalab.org)"}

    for term in candidates:
        try:
            url = (
                f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
                f"&gsrsearch={urllib.parse.quote(term)}&gsrnamespace=6&gsrlimit=6"
                f"&prop=pageimages&pithumbsize=1080&format=json"
            )
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                thumb = page.get("thumbnail", {})
                thumb_url = thumb.get("source")
                if not thumb_url:
                    continue
                lower = thumb_url.lower()
                title_lower = page.get("title", "").lower()
                # Exclude non-images
                if any(bad in title_lower or bad in lower for bad in (".pdf", ".svg", ".webm", ".ogg", ".ogv", ".tif", ".tiff")):
                    continue
                if not any(ext in lower for ext in (".jpg", ".jpeg", ".png")):
                    continue
                dl = requests.get(thumb_url, headers=headers, timeout=12)
                if dl.status_code == 200 and len(dl.content) > 15000:
                    raw_img = Image.open(BytesIO(dl.content)).convert("RGB")
                    if raw_img.width >= 300 and raw_img.height >= 300:
                        logger.info("Found scientific visual for '%s': %s", term, page.get("title", ""))
                        return raw_img
        except Exception as exc:
            logger.debug("Wikimedia search failed for '%s': %s", term, exc)
            continue
    return None


def _render_procedural_base(fi: int, frame_count: int, theme: str, desc_l: str) -> Image.Image:
    img = _new_space_background(fi, frame_count)
    draw = ImageDraw.Draw(img)
    cx, cy = WIDTH // 2, int(HEIGHT * 0.42)
    planet_radius = int(min(WIDTH, HEIGHT) * 0.16)
    show_ring = "saturn" in desc_l or "ring" in desc_l
    _draw_planet(draw, cx, cy, planet_radius, fi, frame_count, ring=show_ring)
    _draw_light_flare(draw, cx - int(planet_radius * 0.9), cy - int(planet_radius * 0.9), fi)
    _draw_particles(draw, fi, count=50)
    return img


def _apply_cinematic_styling(raw_img: Image.Image, scene: dict, scene_index: int, total_scenes: int, theme: str) -> Image.Image:
    # 1. Fit to vertical 1080x1920
    img = ImageOps.fit(raw_img, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)

    # 2. Cinematic Theatrical Color Grading
    from PIL import ImageEnhance
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.12)

    # 3. Ambient Sci-Fi Dark Tint (unifies visual color palette)
    tint = Image.new("RGB", (WIDTH, HEIGHT), (6, 12, 28))
    img = Image.blend(img, tint, 0.14)

    # 4. Cinematic Vignette (darken perimeter, highlight center)
    vignette = Image.new("L", (WIDTH, HEIGHT), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse([(-180, -180), (WIDTH + 180, HEIGHT + 180)], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(110))
    black_bg = Image.new("RGB", (WIDTH, HEIGHT), (4, 6, 14))
    img = Image.composite(img, black_bg, vignette)

    draw = ImageDraw.Draw(img)

    # 5. Glowing particle dust motes
    _draw_particles(draw, scene_index * 15, count=35)

    # 6. Scene overlays
    cx = WIDTH // 2
    if theme == "brain":
        _draw_diagram_brain(draw, (cx, int(HEIGHT * 0.70)), 20)
    elif theme == "question":
        _draw_question_badge(draw, (cx, int(HEIGHT * 0.70)), 15)
    elif theme == "brand":
        _draw_brand_reveal(draw, (cx, int(HEIGHT * 0.70)), 25)
    elif theme == "atom":
        _draw_diagram_atom(draw, (cx, int(HEIGHT * 0.70)), 10)
    elif theme == "orbit":
        _draw_diagram_orbit(draw, (cx, int(HEIGHT * 0.70)), 10)

    # 7. Animated typography / title card
    on_screen_text = scene.get("on_screen_text", "")
    highlight = scene.get("highlight_word") if scene.get("highlight") else None
    if on_screen_text:
        _draw_typography(draw, on_screen_text, (cx, int(HEIGHT * 0.86)),
                         30, 60, highlight_word=highlight)

    return img


def render_scene(scene: dict, scene_index: int, total_scenes: int,
                 output_dir: Path = FRAMES_DIR) -> Path:
    """Render cinematic base image and frames for one scene."""
    scene_dir = output_dir / f"scene_{scene_index:02d}"
    scene_dir.mkdir(parents=True, exist_ok=True)

    description = scene.get("description", "")
    visual_query = scene.get("visual_query") or scene.get("on_screen_text") or description
    desc_l = description.lower()

    # Pick visual theme from the description.
    theme = "space"
    if any(k in desc_l for k in ("brain", "mind", "neuron", "synapse", "memory", "thought", "psychology", "hallucination", "sleep")):
        theme = "brain"
    elif any(k in desc_l for k in ("question", "comment", "how many", "poll", "what do you", "hours do you", "be honest")):
        theme = "question"
    elif any(k in desc_l for k in ("logo", "jigyasa", "outro", "follow", "reveal")):
        theme = "brand"
    elif any(k in desc_l for k in ("atom", "electron", "nucleus", "particle", "physics")):
        theme = "atom"
    elif any(k in desc_l for k in ("orbit", "solar", "planet around", "revolve")):
        theme = "orbit"
    elif any(k in desc_l for k in ("body", "human", "organ", "cell", "dna", "heart")):
        theme = "body"

    logger.info("Generating cinematic scene %d/%d (theme=%s, query='%s')",
                scene_index + 1, total_scenes, theme, visual_query[:40])

    # 1. Fetch authentic scientific visual or fallback to procedural base
    raw_img = _fetch_scientific_visual(visual_query, theme)
    if not raw_img:
        logger.info("Using procedural 3D visual fallback for scene %d", scene_index + 1)
        raw_img = _render_procedural_base(fi=scene_index * 12, frame_count=60, theme=theme, desc_l=desc_l)

    # 2. Apply cinematic color grade, vignette & theatrical branding
    cinematic_img = _apply_cinematic_styling(raw_img, scene, scene_index, total_scenes, theme)

    # 3. Save master high-resolution cinematic base image
    base_path = scene_dir / "cinematic_base.png"
    cinematic_img.save(base_path, quality=95)

    # Save initial preview frames for backward compatibility
    cinematic_img.save(scene_dir / "frame_0000.png", quality=92)
    cinematic_img.save(scene_dir / "frame_0001.png", quality=92)

    log_event("scene_rendered", scene=scene_index, theme=theme,
              cinematic_base=str(base_path))
    return scene_dir


def render_all_scenes(scenes: list[dict]) -> list[Path]:
    """Render frame sequences for every scene. Returns scene directories."""
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    # Clean old frames.
    for old in FRAMES_DIR.glob("scene_*"):
        for f in old.iterdir():
            f.unlink()
        old.rmdir()

    dirs: list[Path] = []
    for i, scene in enumerate(scenes):
        dirs.append(render_scene(scene, i, len(scenes)))
    log_event("all_scenes_rendered", count=len(dirs), frames_dir=str(FRAMES_DIR))
    return dirs
