"""
Central configuration for the video rendering pipeline.
All paths, dimensions, durations, colors, and typography settings live here.
"""

import shutil
from pathlib import Path


def _find_ffmpeg() -> str:
    """Find FFmpeg binary — system PATH first, then imageio-ffmpeg fallback."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"  # Will fail at runtime with a clear error


FFMPEG_BIN = _find_ffmpeg()

# ─── Directory Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
TEMP_DIR = PROJECT_ROOT / "temp"
OUTPUT_DIR = PROJECT_ROOT / "output"
FONTS_DIR = PROJECT_ROOT / "fonts"

# ─── Asset Paths ────────────────────────────────────────────────────────────────
BG_VIDEO = ASSETS_DIR / "bg.mp4"
MUSIC_FILE = ASSETS_DIR / "music.mp3"
LOGO_FILE = ASSETS_DIR / "logo.png"
FONT_BOLD = FONTS_DIR / "Montserrat-Bold.ttf"
FONT_EXTRABOLD = FONT_BOLD  # Use Bold as fallback (ExtraBold is optional)

# Google Fonts direct download URLs — only Bold is required
FONT_URLS = {
    "Montserrat-Bold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
}

# ─── Video Specifications ───────────────────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
CODEC = "libx264"
PRESET = "medium"
CRF = 23
PIXEL_FORMAT = "yuv420p"
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "128k"

# ─── Scene Durations (seconds) ──────────────────────────────────────────────────
SCENE_1_DURATION = 3    # Breaking News intro
SCENE_2_DURATION = 9    # News image + headline
SCENE_3_DURATION = 8    # Description text
SCENE_4_DURATION = 5    # Outro / CTA
XFADE_DURATION = 0.5    # Crossfade between scenes

TOTAL_DURATION = (
    SCENE_1_DURATION + SCENE_2_DURATION + SCENE_3_DURATION + SCENE_4_DURATION
    - 3 * XFADE_DURATION  # 3 transitions overlap
)

# ─── Colors (RGBA) ──────────────────────────────────────────────────────────────
COLOR_BG_DARK = (10, 10, 26)
COLOR_BG_DARK_RGBA = (10, 10, 26, 255)
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_TEXT_SHADOW = (0, 0, 0)
COLOR_ACCENT_RED = (220, 38, 38)
COLOR_ACCENT_ORANGE = (255, 140, 0)
COLOR_OVERLAY = (0, 0, 0, 180)

# ─── Typography ─────────────────────────────────────────────────────────────────
FONT_SIZE_BREAKING = 120
FONT_SIZE_TITLE = 72
FONT_SIZE_HEADLINE = 54
FONT_SIZE_BODY = 46
FONT_SIZE_SMALL = 36
FONT_SIZE_CTA = 42
TEXT_MARGIN = 80
LINE_SPACING = 14
