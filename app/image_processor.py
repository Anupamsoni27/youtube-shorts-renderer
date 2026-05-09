"""
Image processor for news article images.
Downloads, converts, resizes, and applies blur-fill for Shorts format.
"""

import io
from pathlib import Path

import requests
from PIL import Image, ImageFilter

from app import config
from app.utils import logger


def download_image(url: str) -> Image.Image:
    """
    Download an image from a URL and return as a PIL Image.
    Handles GIF (extracts first frame), JPG, PNG, and WebP.
    """
    logger.info(f"Downloading image: {url[:80]}...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Failed to download image: {e}. Using fallback.")
        return _create_fallback_image()

    try:
        img = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        logger.warning(f"Failed to open image: {e}. Using fallback.")
        return _create_fallback_image()

    # Handle animated GIF — extract first frame
    if getattr(img, "is_animated", False):
        logger.info("Animated GIF detected — extracting first frame")
        img.seek(0)

    # Convert to RGB (removes alpha, handles palette modes)
    img = img.convert("RGB")
    logger.info(f"Image downloaded: {img.size[0]}x{img.size[1]}")
    return img


def process_for_shorts(
    img: Image.Image,
    target_w: int = config.VIDEO_WIDTH,
    target_h: int = config.VIDEO_HEIGHT,
) -> Image.Image:
    """
    Process an image for Shorts format (1080x1920).
    
    Strategy:
    1. Create a blurred, darkened copy scaled to fill the full frame.
    2. Scale the original image to fit within the frame (maintaining aspect ratio).
    3. Composite the sharp image centered over the blurred background.
    
    This ensures no black bars and a cinematic look regardless of input aspect ratio.
    """
    # ── Step 1: Create blurred background fill ──
    bg = img.copy()
    # Scale to fill the entire target (crop overflow)
    bg_ratio = max(target_w / bg.width, target_h / bg.height)
    bg_scaled = bg.resize(
        (int(bg.width * bg_ratio), int(bg.height * bg_ratio)),
        Image.Resampling.LANCZOS,
    )
    # Center crop to target
    left = (bg_scaled.width - target_w) // 2
    top = (bg_scaled.height - target_h) // 2
    bg_cropped = bg_scaled.crop((left, top, left + target_w, top + target_h))
    # Apply heavy blur + darken
    bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(radius=40))
    from PIL import ImageEnhance
    bg_blurred = ImageEnhance.Brightness(bg_blurred).enhance(0.4)

    # ── Step 2: Scale original to fit within frame ──
    fit_ratio = min(target_w / img.width, (target_h * 0.55) / img.height)
    fit_w = int(img.width * fit_ratio)
    fit_h = int(img.height * fit_ratio)
    img_fitted = img.resize((fit_w, fit_h), Image.Resampling.LANCZOS)

    # ── Step 3: Composite centered (slightly above center for headline space below) ──
    paste_x = (target_w - fit_w) // 2
    paste_y = (target_h - fit_h) // 2 - int(target_h * 0.08)
    paste_y = max(paste_y, int(target_h * 0.05))  # Don't go too high

    bg_blurred.paste(img_fitted, (paste_x, paste_y))

    logger.info(f"Image processed for Shorts: {target_w}x{target_h}")
    return bg_blurred


def save_processed_image(img: Image.Image, filename: str = "news_image.png") -> Path:
    """Save the processed image to temp directory."""
    output_path = config.TEMP_DIR / filename
    img.save(str(output_path), "PNG")
    logger.info(f"Processed image saved: {output_path}")
    return output_path


def _create_fallback_image() -> Image.Image:
    """Create a dark placeholder image when download fails."""
    from PIL import ImageDraw
    from app.utils import load_font

    img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), config.COLOR_BG_DARK)
    draw = ImageDraw.Draw(img)

    try:
        font = load_font(config.FONT_SIZE_BODY)
    except Exception:
        font = ImageDraw.getfont()

    draw.text(
        (config.VIDEO_WIDTH // 2, config.VIDEO_HEIGHT // 2),
        "IMAGE\nUNAVAILABLE",
        font=font,
        fill=(100, 100, 120),
        anchor="mm",
        align="center",
    )
    return img
