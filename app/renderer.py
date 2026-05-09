"""
Video renderer — orchestrates the full rendering pipeline.

Pipeline:
  1. Download & process news image
  2. Generate scene PNG frames (Pillow)
  3. Animate each scene with zoompan (FFmpeg)
  4. Concatenate scenes with crossfade transitions (FFmpeg)
  5. Composite with background video (FFmpeg)
  6. Add background music (FFmpeg)
  7. Cleanup temp files

This is the main entry point for video generation.
"""

import time
from pathlib import Path

from app import config
from app.ffmpeg_builder import FFmpegBuilder
from app.image_processor import download_image, process_for_shorts, save_processed_image
from app.models import NewsArticle
from app.scene_builder import SceneBuilder
from app.utils import cleanup_temp, logger


class VideoRenderer:
    """
    Orchestrates the full video rendering pipeline.
    
    Usage:
        renderer = VideoRenderer()
        output_path = renderer.render(news_article)
    
    For future integration:
        - Connect to MongoDB for news articles
        - Add AI voice generation step between scene build and FFmpeg
        - Add subtitle overlay step
        - Add multiple template support via SceneBuilder subclasses
    """

    def __init__(self):
        self.ffmpeg = FFmpegBuilder()

    def render(
        self,
        news: NewsArticle,
        output_dir: Path = None,
        output_filename: str = "final_video.mp4",
    ) -> Path:
        """
        Generate a complete YouTube Shorts video from a news article.
        
        Args:
            news: The news article to render
            output_dir: Directory for the final video (default: config.OUTPUT_DIR)
            output_filename: Filename for the final video (default: final_video.mp4)
        
        Returns the path to the final MP4 file.
        """
        if output_dir is None:
            output_dir = config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        logger.info("=" * 60)
        logger.info("STARTING VIDEO RENDER")
        logger.info(f"Title: {news.title[:60]}...")
        logger.info(f"Output: {output_dir / output_filename}")
        logger.info("=" * 60)

        try:
            # ── Step 1: Download and process news image ──
            logger.info("─── Step 1/6: Processing news image ───")
            raw_image = download_image(news.urlToImage)
            processed_image = process_for_shorts(raw_image)
            save_processed_image(processed_image)

            # ── Step 2: Generate scene frames ──
            logger.info("─── Step 2/6: Building scene frames ───")
            builder = SceneBuilder(news, news_image=processed_image)
            scene_pngs = builder.build_all()

            # ── Step 3: Animate scenes with zoompan ──
            logger.info("─── Step 3/6: Animating scenes ───")
            scene_videos = self.ffmpeg.animate_scenes(scene_pngs)

            # ── Step 4: Concatenate with crossfade ──
            logger.info("─── Step 4/6: Concatenating scenes ───")
            concat_video = self.ffmpeg.concatenate_scenes(scene_videos)

            # ── Step 5: Composite with background ──
            logger.info("─── Step 5/6: Compositing with background ───")
            composed_video = self.ffmpeg.composite_with_background(concat_video)

            # ── Step 6: Add music ──
            logger.info("─── Step 6/6: Adding background music ───")
            final_video = self.ffmpeg.add_music(
                composed_video,
                output_path=output_dir / output_filename,
            )

            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info(f"RENDER COMPLETE in {elapsed:.1f}s")
            logger.info(f"Output: {final_video}")
            logger.info(f"Size: {final_video.stat().st_size / (1024*1024):.1f} MB")
            logger.info("=" * 60)

            return final_video

        except Exception as e:
            logger.error(f"Render failed: {e}")
            raise

        finally:
            # Cleanup temp files
            cleanup_temp()

