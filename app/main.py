"""
YouTube Shorts News Video Generator — CLI Entry Point.

Usage:
    python app/main.py

Generates a vertical 1080x1920 MP4 video from a mock news object.
The video is saved to output/final_video.mp4.
"""

import sys
from pathlib import Path

# Add project root to path so we can run from any directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import config
from app.mock_data import get_mock_news
from app.renderer import VideoRenderer
from app.utils import check_ffmpeg, ensure_fonts, logger, setup_dirs


def generate_placeholder_assets() -> None:
    """
    Generate placeholder assets for testing if they don't exist.
    In production, replace these with real assets.
    """
    from app.utils import run_ffmpeg

    # ── Placeholder bg.mp4: dark animated gradient ──
    if not config.BG_VIDEO.exists():
        logger.info("Generating placeholder bg.mp4...")
        cmd = [
            config.FFMPEG_BIN, "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x0a0a1a:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:d=30:r={config.FPS}",
            "-vf", "noise=alls=15:allf=t,eq=brightness=-0.05",
            "-c:v", config.CODEC,
            "-preset", "fast",
            "-pix_fmt", config.PIXEL_FORMAT,
            "-t", "30",
            str(config.BG_VIDEO),
        ]
        run_ffmpeg(cmd, "Generate placeholder background video")

    # ── Placeholder music.mp3: silent audio ──
    if not config.MUSIC_FILE.exists():
        logger.info("Generating placeholder music.mp3 (silent)...")
        cmd = [
            config.FFMPEG_BIN, "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "30",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            str(config.MUSIC_FILE),
        ]
        run_ffmpeg(cmd, "Generate placeholder music (silent)")

    # ── Placeholder logo.png ──
    if not config.LOGO_FILE.exists():
        logger.info("Generating placeholder logo.png...")
        try:
            from PIL import Image, ImageDraw
            from app.utils import load_font

            logo = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            draw = ImageDraw.Draw(logo)
            # Red circle background
            draw.ellipse([10, 10, 190, 190], fill=(220, 38, 38, 240))
            # "N" text
            try:
                font = load_font(100)
            except Exception:
                font = ImageDraw.getfont()
            draw.text((100, 100), "N", font=font, fill=(255, 255, 255), anchor="mm")
            logo.save(str(config.LOGO_FILE), "PNG")
            logger.info("Placeholder logo generated")
        except Exception as e:
            logger.warning(f"Could not generate placeholder logo: {e}")


def main():
    """Main entry point — generates a YouTube Shorts video from mock news data."""
    logger.info("YouTube Shorts News Video Generator")
    logger.info("─" * 40)

    # ── Pre-flight checks ──
    setup_dirs()
    check_ffmpeg()
    ensure_fonts()
    generate_placeholder_assets()

    # ── Load mock news data ──
    news = get_mock_news()
    logger.info(f"News article: {news.title[:60]}...")
    logger.info(f"Source: {news.source_name}")

    # ── Render video ──
    renderer = VideoRenderer()
    output_path = renderer.render(news)

    # ── Done ──
    print("\n" + "=" * 60)
    print(f"✅ Video generated successfully!")
    print(f"📁 Output: {output_path}")
    print(f"📐 Format: {config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT} @ {config.FPS}fps")
    print(f"⏱  Duration: ~{config.TOTAL_DURATION}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
