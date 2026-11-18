"""JIGYASA LAB — 2D Stickman Cartoon Animation Engine (in the viral style of @mrstickman_1).

Generates clean 2D vector cartoon scenes featuring minimalist stickman characters
with expressive facial features, clothing, and props across diverse story settings.
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from config import HEIGHT, WIDTH
from logger import logger, log_event


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


# --- Background Renderers ---

def _draw_beach_setting(draw: ImageDraw.ImageDraw) -> None:
    # Sky
    for y in range(480):
        t = y / 480
        draw.line([(0, y), (WIDTH, y)], fill=(int(215 * (1 - t) + 245 * t),
                                              int(235 * (1 - t) + 250 * t),
                                              int(255 * (1 - t) + 252 * t)))
    # Distant clouds & birds
    draw.arc([140, 120, 260, 180], 0, 180, fill=(255, 255, 255), width=6)
    draw.arc([220, 110, 340, 170], 0, 180, fill=(255, 255, 255), width=6)
    # Birds
    for bx, by in [(540, 160), (620, 140), (680, 175)]:
        draw.arc([bx - 18, by - 10, bx, by + 10], 190, 350, fill=(100, 110, 125), width=3)
        draw.arc([bx, by - 10, bx + 18, by + 10], 190, 350, fill=(100, 110, 125), width=3)

    # Ocean
    for y in range(480, 680):
        t = (y - 480) / 200
        draw.line([(0, y), (WIDTH, y)], fill=(int(125 * (1 - t) + 165 * t),
                                              int(185 * (1 - t) + 210 * t),
                                              int(220 * (1 - t) + 235 * t)))

    # Sand beach
    for y in range(640, HEIGHT):
        t = (y - 640) / (HEIGHT - 640)
        draw.line([(0, y), (WIDTH, y)], fill=(int(248 * (1 - t) + 235 * t),
                                              int(232 * (1 - t) + 212 * t),
                                              int(192 * (1 - t) + 168 * t)))

    # Curving shoreline & smooth gentle wave foam
    wave_pts = [(WIDTH, 620)]
    for y in range(620, HEIGHT + 20, 20):
        x = int(WIDTH * 0.74 + 70 * math.sin(y / 240))
        wave_pts.append((x, y))
    wave_pts.extend([(WIDTH, HEIGHT), (WIDTH, 620)])
    draw.polygon(wave_pts, fill=(145, 195, 225))

    # White foam line along shore
    for y in range(620, HEIGHT, 10):
        x = int(WIDTH * 0.74 + 70 * math.sin(y / 240))
        draw.ellipse([x - 12, y - 4, x + 16, y + 14], fill=(255, 255, 255))
        draw.ellipse([x - 6, y + 2, x + 8, y + 10], fill=(240, 250, 255))

    # Black Luxury Sedan parked on sand
    car_x, car_y = 120, 480
    # Car shadow
    draw.ellipse([car_x - 30, car_y + 110, car_x + 480, car_y + 155], fill=(200, 180, 145))
    # Car body
    draw.polygon([
        (car_x, car_y + 90), (car_x + 90, car_y + 25), (car_x + 320, car_y + 25),
        (car_x + 420, car_y + 80), (car_x + 440, car_y + 120), (car_x - 15, car_y + 120)
    ], fill=(42, 45, 52), outline=(15, 18, 22), width=4)
    # Tinted windows
    draw.polygon([
        (car_x + 105, car_y + 35), (car_x + 305, car_y + 35),
        (car_x + 295, car_y + 80), (car_x + 95, car_y + 80)
    ], fill=(160, 190, 210), outline=(20, 22, 26), width=3)
    # Chrome trim & wheels
    draw.line([(car_x + 10, car_y + 95), (car_x + 430, car_y + 95)], fill=(180, 190, 205), width=3)
    for wx in (car_x + 85, car_x + 350):
        draw.ellipse([wx - 36, car_y + 90, wx + 36, car_y + 160], fill=(22, 24, 28))
        draw.ellipse([wx - 20, car_y + 105, wx + 20, car_y + 145], fill=(190, 195, 205), outline=(50, 55, 65), width=3)


def _draw_office_setting(draw: ImageDraw.ImageDraw) -> None:
    # Wall / window background
    for y in range(HEIGHT):
        if y < 850:
            # City view sky
            draw.line([(0, y), (WIDTH, y)], fill=(210, 225, 245))
        else:
            # Polished wooden floor
            draw.line([(0, y), (WIDTH, y)], fill=(int(185 - (y - 850) * 0.08), 130, 95))

    # City skyscraper silhouettes outside window
    buildings = [(50, 420, 140), (220, 360, 110), (360, 480, 150), (540, 390, 160), (740, 440, 130)]
    for bx, by, bw in buildings:
        draw.rectangle([bx, by, bx + bw, 850], fill=(165, 185, 210), outline=(140, 160, 185), width=2)
        # Window grids
        for wy in range(by + 25, 820, 40):
            for wx in range(bx + 15, bx + bw - 15, 30):
                draw.rectangle([wx, wy, wx + 12, wy + 20], fill=(240, 248, 255))

    # Big office glass mullions
    for mx in (200, 500, 800):
        draw.line([(mx, 0), (mx, 850)], fill=(70, 75, 85), width=8)
    draw.line([(0, 850), (WIDTH, 850)], fill=(50, 55, 65), width=10)

    # Modern desk
    desk_y = 960
    draw.polygon([(180, desk_y), (900, desk_y), (960, desk_y + 180), (120, desk_y + 180)],
                 fill=(235, 238, 242), outline=(40, 45, 55), width=4)
    # Desk legs
    draw.line([(180, desk_y + 180), (180, desk_y + 350)], fill=(80, 85, 95), width=10)
    draw.line([(900, desk_y + 180), (900, desk_y + 350)], fill=(80, 85, 95), width=10)
    # Laptop
    draw.polygon([(460, desk_y + 40), (620, desk_y + 40), (600, desk_y + 130), (440, desk_y + 130)],
                 fill=(190, 195, 205), outline=(30, 35, 45), width=3)
    draw.polygon([(460, desk_y + 40), (620, desk_y + 40), (630, desk_y - 70), (470, desk_y - 70)],
                 fill=(40, 45, 55), outline=(20, 25, 35), width=3)


def _draw_room_setting(draw: ImageDraw.ImageDraw) -> None:
    # Wall
    for y in range(HEIGHT):
        if y < 900:
            draw.line([(0, y), (WIDTH, y)], fill=(240, 235, 225))
        else:
            draw.line([(0, y), (WIDTH, y)], fill=(160, 120, 90))
    draw.line([(0, 900), (WIDTH, 900)], fill=(100, 70, 50), width=6)

    # Wall clock
    draw.ellipse([480, 220, 600, 340], fill=(255, 255, 255), outline=(40, 40, 40), width=6)
    draw.line([(540, 280), (540, 240)], fill=(20, 20, 20), width=5)
    draw.line([(540, 280), (575, 280)], fill=(20, 20, 20), width=4)
    draw.ellipse([536, 276, 544, 284], fill=(220, 50, 50))


def _draw_classroom_setting(draw: ImageDraw.ImageDraw) -> None:
    # Classroom wall
    for y in range(HEIGHT):
        if y < 880:
            draw.line([(0, y), (WIDTH, y)], fill=(235, 238, 232))
        else:
            draw.line([(0, y), (WIDTH, y)], fill=(150, 120, 90))
    draw.line([(0, 880), (WIDTH, 880)], fill=(80, 50, 30), width=8)

    # Big Green Chalkboard
    board_rect = [80, 160, WIDTH - 80, 660]
    draw.rectangle(board_rect, fill=(38, 75, 52), outline=(135, 85, 45), width=12)
    # Chalk drawings on board
    font = _get_font(36, bold=True)
    draw.text((140, 220), "PRIORITIES = TIME", font=font, fill=(230, 240, 230))
    draw.line([(140, 275), (550, 275)], fill=(230, 240, 230), width=3)
    # Jar drawing with rocks & pebbles on chalkboard
    draw.arc([720, 240, 860, 300], 180, 360, fill=(240, 245, 240), width=4)
    draw.line([(720, 270), (720, 540)], fill=(240, 245, 240), width=4)
    draw.line([(860, 270), (860, 540)], fill=(240, 245, 240), width=4)
    draw.arc([720, 510, 860, 570], 0, 180, fill=(240, 245, 240), width=4)
    # Rocks inside jar
    draw.ellipse([740, 460, 790, 510], fill=(55, 95, 70), outline=(230, 240, 230), width=3)
    draw.ellipse([780, 450, 840, 510], fill=(55, 95, 70), outline=(230, 240, 230), width=3)
    draw.ellipse([755, 390, 815, 450], fill=(55, 95, 70), outline=(230, 240, 230), width=3)


def _draw_park_setting(draw: ImageDraw.ImageDraw) -> None:
    # Sky
    for y in range(700):
        t = y / 700
        draw.line([(0, y), (WIDTH, y)], fill=(int(200 * (1 - t) + 240 * t),
                                              int(225 * (1 - t) + 248 * t),
                                              int(255 * (1 - t) + 252 * t)))
    # Distant mountains
    draw.polygon([(0, 680), (220, 500), (450, 680)], fill=(175, 195, 215))
    draw.polygon([(350, 680), (600, 460), (850, 680)], fill=(160, 185, 205))

    # Green Grass Hill
    for y in range(680, HEIGHT):
        t = (y - 680) / (HEIGHT - 680)
        draw.line([(0, y), (WIDTH, y)], fill=(int(145 * (1 - t) + 115 * t),
                                              int(195 * (1 - t) + 165 * t),
                                              int(95 * (1 - t) + 75 * t)))

    # Big Tree on left
    draw.polygon([(140, 850), (190, 850), (180, 380), (150, 380)], fill=(110, 75, 45), outline=(0, 0, 0), width=4)
    draw.ellipse([40, 200, 290, 450], fill=(95, 165, 80), outline=(0, 0, 0), width=5)
    draw.ellipse([110, 140, 360, 390], fill=(115, 185, 95), outline=(0, 0, 0), width=5)

    # Wooden Park Bench
    bx = 480
    by = 750
    draw.line([(bx, by), (bx + 260, by)], fill=(140, 85, 45), width=14)
    draw.line([(bx, by + 30), (bx + 260, by + 30)], fill=(140, 85, 45), width=14)
    draw.line([(bx + 20, by + 40), (bx + 20, by + 120)], fill=(40, 45, 50), width=8)
    draw.line([(bx + 240, by + 40), (bx + 240, by + 120)], fill=(40, 45, 50), width=8)


def _draw_city_setting(draw: ImageDraw.ImageDraw) -> None:
    # Sky & Sunset
    for y in range(750):
        t = y / 750
        draw.line([(0, y), (WIDTH, y)], fill=(int(245 * (1 - t) + 250 * t),
                                              int(190 * (1 - t) + 215 * t),
                                              int(160 * (1 - t) + 195 * t)))

    # City Skyline
    bldgs = [(30, 340, 150), (200, 280, 180), (400, 380, 160), (580, 250, 200), (800, 360, 180)]
    for bx, by, bw in bldgs:
        draw.rectangle([bx, by, bx + bw, 750], fill=(65, 72, 85), outline=(0, 0, 0), width=3)
        for wy in range(by + 20, 720, 45):
            for wx in range(bx + 15, bx + bw - 15, 35):
                draw.rectangle([wx, wy, wx + 16, wy + 24], fill=(255, 235, 160))

    # Road & Sidewalk
    draw.rectangle([0, 750, WIDTH, 860], fill=(185, 190, 195), outline=(130, 135, 140), width=4)
    draw.rectangle([0, 860, WIDTH, HEIGHT], fill=(55, 60, 68))
    # Road dash lines
    for x in range(40, WIDTH, 120):
        draw.rectangle([x, 1050, x + 60, 1070], fill=(245, 215, 60))


# --- Stickman Character Drawer ---

def _draw_stickman_head(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 75,
                        expr: str = "open", looking: str = "left") -> None:
    """The iconic @mrstickman_1 bald white head with expressive black features."""
    # Head circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255), outline=(0, 0, 0), width=5)

    eye_off = -15 if looking == "left" else (15 if looking == "right" else 0)
    e1_x = cx - 28 + eye_off
    e2_x = cx + 22 + eye_off

    # Eyes & Eyebrows
    if expr in ("happy", "smile"):
        # Smiling curved eyes ^ ^
        for ex in (e1_x, e2_x):
            draw.arc([ex - 16, cy - 18, ex + 16, cy + 12], 200, 340, fill=(0, 0, 0), width=5)
            draw.line([(ex - 16, cy - 30), (ex + 14, cy - 26)], fill=(0, 0, 0), width=4)
    elif expr in ("closed", "relaxed"):
        # Sleeping/closed curved lines
        for ex in (e1_x, e2_x):
            draw.arc([ex - 15, cy - 10, ex + 15, cy + 12], 10, 170, fill=(0, 0, 0), width=4)
            draw.line([(ex - 15, cy - 24), (ex + 12, cy - 22)], fill=(0, 0, 0), width=4)
    elif expr in ("shocked", "surprised"):
        # Huge round eyes
        for ex in (e1_x, e2_x):
            draw.ellipse([ex - 20, cy - 22, ex + 20, cy + 22], fill=(255, 255, 255), outline=(0, 0, 0), width=4)
            draw.ellipse([ex - 7, cy - 7, ex + 7, cy + 7], fill=(0, 0, 0))
            draw.arc([ex - 22, cy - 45, ex + 22, cy - 25], 190, 350, fill=(0, 0, 0), width=4)
    else:
        # Classic open eyes looking at other character
        for ex in (e1_x, e2_x):
            draw.ellipse([ex - 18, cy - 20, ex + 18, cy + 20], fill=(255, 255, 255), outline=(0, 0, 0), width=4)
            pupil_shift = -6 if looking == "left" else (6 if looking == "right" else 0)
            draw.ellipse([ex - 8 + pupil_shift, cy - 8, ex + 8 + pupil_shift, cy + 8], fill=(0, 0, 0))
            draw.line([(ex - 18, cy - 30), (ex + 16, cy - 26)], fill=(0, 0, 0), width=4)

    # Mouth
    if expr in ("happy", "smile"):
        draw.arc([cx - 22, cy + 8, cx + 22, cy + 38], 20, 160, fill=(0, 0, 0), width=5)
    elif expr in ("talk", "talking"):
        draw.ellipse([cx - 16, cy + 16, cx + 16, cy + 42], fill=(40, 20, 20), outline=(0, 0, 0), width=4)
    elif expr in ("shocked", "surprised"):
        draw.ellipse([cx - 18, cy + 15, cx + 18, cy + 50], fill=(30, 20, 20), outline=(0, 0, 0), width=4)
    else:
        # Subtle smirk / line
        draw.line([(cx - 18, cy + 26), (cx + 18, cy + 26)], fill=(0, 0, 0), width=4)


def _draw_businessman(draw: ImageDraw.ImageDraw, x: int, y: int, expr: str = "open",
                      pose: str = "talking", looking: str = "left") -> None:
    """Stickman in grey tailored business suit & tie."""
    # Head
    _draw_stickman_head(draw, x, y, r=76, expr=expr, looking=looking)

    # Suit Torso
    torso_top = y + 76
    torso_bottom = torso_top + 190
    draw.polygon([
        (x - 48, torso_top + 10), (x + 48, torso_top + 10),
        (x + 40, torso_bottom), (x - 40, torso_bottom)
    ], fill=(92, 102, 118), outline=(0, 0, 0), width=5)

    # White Collar & Tie
    draw.polygon([(x - 16, torso_top + 10), (x + 16, torso_top + 10), (x, torso_top + 35)],
                 fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    draw.polygon([(x - 8, torso_top + 30), (x + 8, torso_top + 30),
                  (x + 10, torso_top + 130), (x, torso_top + 150), (x - 10, torso_top + 130)],
                 fill=(25, 28, 34))

    # Trousers / Legs
    draw.line([(x - 22, torso_bottom), (x - 22, torso_bottom + 170)], fill=(0, 0, 0), width=8)
    draw.line([(x + 22, torso_bottom), (x + 22, torso_bottom + 170)], fill=(0, 0, 0), width=8)
    # Dress shoes
    draw.ellipse([x - 45, torso_bottom + 165, x - 5, torso_bottom + 195], fill=(20, 20, 25))
    draw.ellipse([x + 5, torso_bottom + 165, x + 45, torso_bottom + 195], fill=(20, 20, 25))

    # Arms
    if pose in ("talking", "gesturing"):
        # One hand gesturing outward
        draw.line([(x - 45, torso_top + 30), (x - 90, torso_top + 80), (x - 145, torso_top + 60)],
                  fill=(0, 0, 0), width=7)
        draw.ellipse([x - 165, torso_top + 50, x - 138, torso_top + 78], fill=(25, 25, 30))
        # Other hand at side
        draw.line([(x + 45, torso_top + 30), (x + 60, torso_top + 120)], fill=(0, 0, 0), width=7)
        draw.ellipse([x + 50, torso_top + 115, x + 75, torso_top + 138], fill=(25, 25, 30))
    elif pose in ("arms_crossed", "cross"):
        draw.line([(x - 45, torso_top + 30), (x + 25, torso_top + 90)], fill=(0, 0, 0), width=8)
        draw.line([(x + 45, torso_top + 30), (x - 25, torso_top + 90)], fill=(0, 0, 0), width=8)
    else:
        # Neutral arms
        draw.line([(x - 45, torso_top + 30), (x - 55, torso_top + 120)], fill=(0, 0, 0), width=7)
        draw.line([(x + 45, torso_top + 30), (x + 55, torso_top + 120)], fill=(0, 0, 0), width=7)


def _draw_fisherman(draw: ImageDraw.ImageDraw, x: int, y: int, expr: str = "happy",
                    pose: str = "reclining", looking: str = "right") -> None:
    """Stickman fisherman with bucket hat, khaki clothes, and fishing rod."""
    # Head
    _draw_stickman_head(draw, x, y, r=72, expr=expr, looking=looking)

    # Bucket Hat
    hat_y = y - 90
    draw.polygon([(x - 85, hat_y + 45), (x + 85, hat_y + 45), (x + 60, hat_y), (x - 60, hat_y)],
                 fill=(145, 140, 110), outline=(0, 0, 0), width=5)
    draw.ellipse([x - 100, hat_y + 35, x + 100, hat_y + 60], fill=(155, 150, 120), outline=(0, 0, 0), width=4)

    if pose in ("reclining", "sitting"):
        # Sand dune support under fisherman back
        draw.polygon([(x - 140, y + 240), (x - 60, y + 70), (x + 40, y + 240)],
                     fill=(235, 215, 175), outline=(195, 175, 135), width=3)
        # Reclining body on sand
        draw.polygon([(x - 45, y + 65), (x + 55, y + 85), (x + 40, y + 190), (x - 60, y + 170)],
                     fill=(172, 168, 132), outline=(0, 0, 0), width=5)
        # Legs bent comfortably on sand
        draw.line([(x + 35, y + 185), (x + 105, y + 220), (x + 160, y + 175), (x + 220, y + 225)],
                  fill=(125, 130, 105), width=18)
        draw.ellipse([x + 210, y + 215, x + 245, y + 245], fill=(135, 105, 75), outline=(0, 0, 0), width=3)
        # Relaxed arm resting on torso
        draw.line([(x - 30, y + 95), (x + 20, y + 125)], fill=(0, 0, 0), width=6)
        draw.ellipse([x + 15, y + 118, x + 38, y + 140], fill=(20, 20, 20))
    else:
        # Standing fisherman
        draw.polygon([(x - 42, y + 72), (x + 42, y + 72), (x + 36, y + 230), (x - 36, y + 230)],
                     fill=(172, 168, 132), outline=(0, 0, 0), width=5)
        draw.line([(x - 18, y + 230), (x - 18, y + 360)], fill=(125, 130, 105), width=18)
        draw.line([(x + 18, y + 230), (x + 18, y + 360)], fill=(125, 130, 105), width=18)
        draw.ellipse([x - 35, y + 355, x - 5, y + 380], fill=(135, 105, 75))
        draw.ellipse([x + 5, y + 355, x + 35, y + 380], fill=(135, 105, 75))

    # Forked stick propping rod
    draw.line([(x - 50, y + 240), (x - 50, y + 130)], fill=(110, 75, 45), width=6)
    draw.line([(x - 50, y + 150), (x - 30, y + 125)], fill=(110, 75, 45), width=5)
    # Fishing Rod
    draw.line([(x - 100, y + 220), (x - 45, y + 130), (x + 25, y - 160)], fill=(75, 45, 20), width=6)
    draw.line([(x + 25, y - 160), (WIDTH * 0.78, HEIGHT * 0.78)], fill=(225, 225, 225), width=2)
    # Bucket
    draw.polygon([(x + 110, y + 140), (x + 175, y + 140), (x + 160, y + 200), (x + 125, y + 200)],
                 fill=(175, 185, 195), outline=(0, 0, 0), width=4)


# --- Master Scene Renderer ---

def render_stickman_scene(scene: dict, scene_index: int, total_scenes: int,
                          output_path: Path) -> Path:
    """Render a complete 2D cartoon stickman panel and save to output_path."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (240, 245, 252))
    draw = ImageDraw.Draw(img)

    setting = scene.get("setting", "beach_car").lower()
    if any(k in setting for k in ("beach", "sea", "ocean", "coast", "shore")):
        _draw_beach_setting(draw)
    elif any(k in setting for k in ("office", "desk", "building", "work")):
        _draw_office_setting(draw)
    elif any(k in setting for k in ("classroom", "school", "chalkboard", "board")):
        _draw_classroom_setting(draw)
    elif any(k in setting for k in ("park", "tree", "bench", "grass", "outdoor")):
        _draw_park_setting(draw)
    elif any(k in setting for k in ("city", "street", "road", "urban")):
        _draw_city_setting(draw)
    else:
        _draw_room_setting(draw)

    char_left = str(scene.get("character_left", "")).lower()
    char_right = str(scene.get("character_right", "")).lower()
    action = str(scene.get("action", "")).lower()

    # Draw Left Character
    if "fisherman" in char_left or "relax" in char_left or "casual" in char_left:
        expr = "happy" if "happy" in action or "smile" in action else "closed"
        _draw_fisherman(draw, 270, 1180, expr=expr, pose="reclining", looking="right")
    elif "businessman" in char_left or "suit" in char_left:
        _draw_businessman(draw, 270, 880, expr="talking", pose="gesturing", looking="right")

    # Draw Right Character
    if "businessman" in char_right or "suit" in char_right or "rich" in char_right:
        expr = "shocked" if "shock" in action or "twist" in action else "open"
        pose = "arms_crossed" if "cross" in action else "talking"
        _draw_businessman(draw, 780, 780, expr=expr, pose=pose, looking="left")
    elif "fisherman" in char_right:
        _draw_fisherman(draw, 780, 1180, expr="happy", pose="sitting", looking="left")

    # Dynamic Center-Screen Subtitle / Word-Burst (just like @mrstickman_1)
    on_screen_text = scene.get("on_screen_text", "").strip()
    if on_screen_text:
        caption_font = _get_font(68, bold=True)
        cx, cy = WIDTH // 2, int(HEIGHT * 0.44)
        draw.text((cx, cy), on_screen_text, font=caption_font, anchor="mm",
                  fill=(255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0))

    # Watermark Brand Tag
    tag_font = _get_font(26, bold=True)
    draw.text((WIDTH - 40, 60), "@JIGYASALAB", font=tag_font, anchor="rt",
              fill=(120, 130, 145))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=95)
    log_event("stickman_scene_rendered", scene=scene_index, setting=setting,
              output=str(output_path))
    return output_path
