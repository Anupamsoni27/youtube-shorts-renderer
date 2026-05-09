from __future__ import annotations

"""
Utility functions for the video rendering pipeline.
Handles text wrapping, directory management, font loading, and logging.
"""

import logging
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

from app import config

# ─── Logging Setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("video_renderer")


def setup_dirs() -> None:
    """Create required directories if they don't exist."""
    for d in [config.ASSETS_DIR, config.TEMP_DIR, config.OUTPUT_DIR, config.FONTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("Directories verified: assets/ temp/ output/ fonts/")


def cleanup_temp() -> None:
    """Remove all files in the temp directory after rendering."""
    if config.TEMP_DIR.exists():
        for f in config.TEMP_DIR.iterdir():
            f.unlink()
        logger.info("Temp directory cleaned")


def check_ffmpeg() -> bool:
    """Verify FFmpeg is installed and accessible."""
    ffmpeg_bin = config.FFMPEG_BIN
    if not Path(ffmpeg_bin).exists() and shutil.which(ffmpeg_bin) is None:
        logger.error("FFmpeg not found! Install with: brew install ffmpeg")
        logger.error("Or install via pip: pip install imageio-ffmpeg")
        sys.exit(1)
    result = subprocess.run(
        [ffmpeg_bin, "-version"], capture_output=True, text=True
    )
    version_line = result.stdout.split("\n")[0]
    logger.info(f"FFmpeg found: {version_line}")
    return True


def ensure_fonts() -> None:
    """Download fonts from Google Fonts if not already present."""
    for filename, url in config.FONT_URLS.items():
        font_path = config.FONTS_DIR / filename
        if font_path.exists():
            continue
        logger.info(f"Downloading font: {filename}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            font_path.write_bytes(resp.content)
            logger.info(f"Font saved: {font_path}")
        except requests.RequestException as e:
            logger.error(f"Failed to download font {filename}: {e}")
            sys.exit(1)


def ensure_r2_assets() -> None:
    """
    Ensure base assets (bg.mp4, music.mp3, logo.png) are present in the assets/ folder.
    If they are missing, automatically download them from the Cloudflare R2 bucket.
    This enables seamless deployments on Render without pushing massive files to Git.
    """
    import os
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Map of local files to their respective target filenames in Cloudflare R2
    assets_to_sync = {
        config.BG_VIDEO: "bg.mp4",
        config.MUSIC_FILE: "music.mp3",
        config.LOGO_FILE: "logo.png"
    }

    # Only sync if there is actually at least one missing file
    missing_assets = {path: key for path, key in assets_to_sync.items() if not path.exists()}
    if not missing_assets:
        return

    from app.r2_storage import get_r2_client
    s3 = get_r2_client()
    if s3 is None:
        logger.info("Some base assets are missing locally, and Cloudflare R2 is not configured to auto-download them.")
        return

    bucket_name = os.getenv("R2_BUCKET_NAME")
    for local_path, r2_key in missing_assets.items():
        logger.info(f"Asset missing: {local_path.name} — Attempting auto-download from Cloudflare R2 bucket: {bucket_name}...")
        try:
            s3.download_file(bucket_name, r2_key, str(local_path))
            logger.info(f"Asset auto-downloaded successfully: {local_path.name}")
        except Exception as e:
            logger.warning(
                f"Could not auto-download {local_path.name} from R2 (skipping and using fallback mode): {e}"
            )


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load a Montserrat font at the specified size."""
    font_path = config.FONT_EXTRABOLD if not bold else config.FONT_BOLD
    # Fallback to bold if extrabold not found
    if not font_path.exists():
        font_path = config.FONT_BOLD
    return ImageFont.truetype(str(font_path), size)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Word-wrap text to fit within max_width pixels using the given font.
    Returns a list of lines.
    """
    words = text.split()
    lines = []
    current_line = ""

    dummy_img = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = dummy_img.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple = config.COLOR_TEXT_WHITE,
    shadow_color: tuple = config.COLOR_TEXT_SHADOW,
    shadow_offset: int = 3,
    anchor: Optional[str] = None,
) -> None:
    """Draw text with a drop shadow for readability over any background."""
    x, y = position
    # Shadow
    draw.text(
        (x + shadow_offset, y + shadow_offset),
        text, font=font, fill=shadow_color, anchor=anchor,
    )
    # Main text
    draw.text(position, text, font=font, fill=fill, anchor=anchor)


def draw_multiline_center(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    y_start: int,
    canvas_width: int,
    fill: tuple = config.COLOR_TEXT_WHITE,
    shadow_offset: int = 3,
    line_spacing: int = config.LINE_SPACING,
) -> int:
    """
    Draw multiple centered lines of text with shadow.
    Returns the y position after the last line.
    """
    y = y_start
    for line in lines:
        draw_text_with_shadow(
            draw, (canvas_width // 2, y), line, font,
            fill=fill, shadow_offset=shadow_offset, anchor="mt",
        )
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = bbox[3] - bbox[1]
        y += line_height + line_spacing
    return y


def format_date(iso_string: str) -> str:
    """Format ISO date string into a human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        return ""


def run_ffmpeg(cmd: list[str], description: str = "") -> bool:
    """
    Execute an FFmpeg command via subprocess.
    Logs the command and handles errors.
    Automatically limits threading to 1 thread to avoid OOM crashes on
    low-memory hosting platforms like Render.com.
    """
    # Force single-threaded execution to heavily reduce RAM/CPU usage on constrained servers
    if cmd and "ffmpeg" in str(cmd[0]).lower():
        # Insert "-threads 1" immediately after the ffmpeg binary path
        cmd.insert(1, "-threads")
        cmd.insert(2, "1")

    logger.info(f"FFmpeg: {description}")
    logger.debug(f"Command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg failed: {description}")
        logger.error(f"stderr: {result.stderr[-500:]}")
        return False

    return True
