from __future__ import annotations

"""
Scene builder — generates static PNG frames for each video scene using Pillow.
FFmpeg handles all animation (zoompan, fades) from these static frames.

Scene Layout:
  Scene 1 (3s): BREAKING NEWS intro — bold red/white text, dark background
  Scene 2 (9s): News image with headline — blur-fill bg + headline at bottom
  Scene 3 (8s): Description text — dark gradient, centered readable text
  Scene 4 (5s): Outro / CTA — source name, follow prompt, logo
"""

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter

from app import config
from app.models import NewsArticle
from app.utils import (
    draw_multiline_center,
    draw_text_with_shadow,
    load_font,
    logger,
    wrap_text,
)


class SceneBuilder:
    """Generates scene PNG frames for the video pipeline."""

    def __init__(self, news: NewsArticle, news_image: Optional[Image.Image] = None):
        self.news = news
        self.news_image = news_image
        self.w = config.VIDEO_WIDTH
        self.h = config.VIDEO_HEIGHT

    def build_all(self) -> list[Path]:
        """Generate all scene PNGs and return their paths."""
        scenes = [
            self._build_scene_1(),
            self._build_scene_2(),
            self._build_scene_3(),
            self._build_scene_4(),
        ]
        logger.info(f"All {len(scenes)} scene frames generated")
        return scenes

    # ─── Scene 1: BREAKING NEWS Intro ───────────────────────────────────────────

    def _build_scene_1(self) -> Path:
        """
        BREAKING NEWS intro screen.
        - Dark gradient background
        - Red accent bar
        - Large "BREAKING" text in red/orange
        - "NEWS" text in white below
        - Logo at top
        """
        canvas = self._dark_gradient_bg()
        draw = ImageDraw.Draw(canvas)

        # Red accent bar across the middle area
        bar_y = self.h // 2 - 120
        bar_h = 240
        bar_overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(bar_overlay)
        bar_draw.rectangle(
            [0, bar_y, self.w, bar_y + bar_h],
            fill=(180, 20, 20, 200),
        )
        canvas = Image.alpha_composite(canvas.convert("RGBA"), bar_overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        # "BREAKING" text
        font_breaking = load_font(config.FONT_SIZE_BREAKING)
        draw_text_with_shadow(
            draw,
            (self.w // 2, self.h // 2 - 60),
            "BREAKING",
            font_breaking,
            fill=config.COLOR_TEXT_WHITE,
            shadow_offset=4,
            anchor="mm",
        )

        # "NEWS" text
        font_news = load_font(config.FONT_SIZE_TITLE)
        draw_text_with_shadow(
            draw,
            (self.w // 2, self.h // 2 + 70),
            "NEWS",
            font_news,
            fill=config.COLOR_TEXT_WHITE,
            shadow_offset=3,
            anchor="mm",
        )

        # Thin red lines above and below the bar
        line_color = config.COLOR_ACCENT_RED
        draw.line([(50, bar_y - 5), (self.w - 50, bar_y - 5)], fill=line_color, width=3)
        draw.line(
            [(50, bar_y + bar_h + 5), (self.w - 50, bar_y + bar_h + 5)],
            fill=line_color, width=3,
        )

        # Logo at top
        self._paste_logo(canvas, y_pos=120)

        # Date at bottom
        from app.utils import format_date
        date_str = format_date(self.news.publishedAt)
        if date_str:
            font_date = load_font(config.FONT_SIZE_SMALL)
            draw = ImageDraw.Draw(canvas)
            draw_text_with_shadow(
                draw,
                (self.w // 2, self.h // 2 + 280),
                date_str,
                font_date,
                fill=(200, 200, 200),
                shadow_offset=2,
                anchor="mm",
            )

        return self._save(canvas, "scene1.png")

    # ─── Scene 2: News Image + Headline ─────────────────────────────────────────

    def _build_scene_2(self) -> Path:
        """
        News image with headline overlay.
        - Processed news image (blur-fill background)
        - Dark gradient overlay at bottom
        - Headline text at bottom
        """
        if self.news_image is not None:
            canvas = self.news_image.copy()
            if canvas.size != (self.w, self.h):
                canvas = canvas.resize((self.w, self.h), Image.Resampling.LANCZOS)
        else:
            canvas = self._dark_gradient_bg()

        # Dark gradient overlay at bottom for text readability
        overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        # Gradient: transparent at top → dark at bottom
        gradient_start = int(self.h * 0.5)
        for y in range(gradient_start, self.h):
            progress = (y - gradient_start) / (self.h - gradient_start)
            alpha = int(220 * progress)
            overlay_draw.line([(0, y), (self.w, y)], fill=(0, 0, 0, alpha))

        canvas_rgba = canvas.convert("RGBA")
        canvas = Image.alpha_composite(canvas_rgba, overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)

        # Headline text safely above bottom overlay
        font_headline = load_font(config.FONT_SIZE_HEADLINE)
        max_text_w = self.w - config.TEXT_MARGIN * 2
        lines = wrap_text(self.news.title, font_headline, max_text_w)

        # Position text from safe lower-middle boundary
        line_h = config.FONT_SIZE_HEADLINE + config.LINE_SPACING
        total_text_h = len(lines) * line_h
        y_start = self.h - total_text_h - 450

        draw_multiline_center(
            draw, lines, font_headline, y_start, self.w,
            fill=config.COLOR_TEXT_WHITE, shadow_offset=3,
        )

        # Source badge centered horizontally and nested right above headline
        font_source = load_font(config.FONT_SIZE_SMALL)
        badge_text = f"  {self.news.source_name.upper()}  "
        bbox = draw.textbbox((0, 0), badge_text, font=font_source)
        badge_w = bbox[2] - bbox[0] + 20
        badge_h = bbox[3] - bbox[1] + 16

        badge_x = (self.w - badge_w) // 2
        badge_y = y_start - badge_h - 40

        # Red badge background
        badge_overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(badge_overlay)
        badge_draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=6,
            fill=(220, 38, 38, 220),
        )
        canvas = Image.alpha_composite(canvas.convert("RGBA"), badge_overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        draw.text((badge_x + 10, badge_y + 8), badge_text, font=font_source, fill=config.COLOR_TEXT_WHITE)

        return self._save(canvas, "scene2.png")

    # ─── Scene 3: Description Text ──────────────────────────────────────────────

    def _build_scene_3(self) -> Path:
        """
        Description text on dark background.
        - Dark gradient background
        - Large quotation mark accent
        - Description text centered
        - Source attribution at bottom
        """
        canvas = self._dark_gradient_bg(top_color=(15, 15, 40), bottom_color=(5, 5, 15))
        draw = ImageDraw.Draw(canvas)

        # Large decorative quotation mark
        try:
            font_quote = load_font(200)
            draw.text(
                (80, self.h // 2 - 350),
                "\u201C",  # Left double quotation mark
                font=font_quote,
                fill=(220, 38, 38, 80) if len(config.COLOR_ACCENT_RED) == 4 else (*config.COLOR_ACCENT_RED, 80),
            )
        except Exception:
            pass

        # Description text — centered
        font_body = load_font(config.FONT_SIZE_BODY)
        max_text_w = self.w - config.TEXT_MARGIN * 2 - 40
        lines = wrap_text(self.news.description, font_body, max_text_w)

        line_h = config.FONT_SIZE_BODY + config.LINE_SPACING + 4
        total_text_h = len(lines) * line_h
        y_start = (self.h - total_text_h) // 2

        draw_multiline_center(
            draw, lines, font_body, y_start, self.w,
            fill=config.COLOR_TEXT_WHITE, shadow_offset=2,
            line_spacing=config.LINE_SPACING + 4,
        )

        # Source name at bottom
        font_source = load_font(config.FONT_SIZE_SMALL)
        draw_text_with_shadow(
            draw,
            (self.w // 2, self.h - 250),
            f"— {self.news.source_name}",
            font_source,
            fill=(180, 180, 190),
            shadow_offset=2,
            anchor="mm",
        )

        # Thin accent line
        line_y = self.h - 300
        draw.line(
            [(self.w // 2 - 100, line_y), (self.w // 2 + 100, line_y)],
            fill=config.COLOR_ACCENT_RED, width=3,
        )

        return self._save(canvas, "scene3.png")

    # ─── Scene 4: Outro / CTA ──────────────────────────────────────────────────

    def _build_scene_4(self) -> Path:
        """
        Outro screen with call-to-action.
        - Dark background
        - Source name
        - "Follow for more updates"
        - Logo
        """
        canvas = self._dark_gradient_bg(top_color=(10, 10, 30), bottom_color=(5, 5, 15))
        draw = ImageDraw.Draw(canvas)

        # Logo centered
        self._paste_logo(canvas, y_pos=self.h // 2 - 250, size=180)
        draw = ImageDraw.Draw(canvas)

        # Source name
        font_title = load_font(config.FONT_SIZE_TITLE)
        draw_text_with_shadow(
            draw,
            (self.w // 2, self.h // 2),
            self.news.source_name,
            font_title,
            fill=config.COLOR_TEXT_WHITE,
            shadow_offset=3,
            anchor="mm",
        )

        # Red accent line
        draw.line(
            [(self.w // 2 - 120, self.h // 2 + 50), (self.w // 2 + 120, self.h // 2 + 50)],
            fill=config.COLOR_ACCENT_RED, width=3,
        )

        # CTA text
        font_cta = load_font(config.FONT_SIZE_CTA)
        draw_text_with_shadow(
            draw,
            (self.w // 2, self.h // 2 + 120),
            "Follow for more updates",
            font_cta,
            fill=(200, 200, 210),
            shadow_offset=2,
            anchor="mm",
        )

        # Subscribe-style prompt
        font_small = load_font(config.FONT_SIZE_SMALL)
        draw_text_with_shadow(
            draw,
            (self.w // 2, self.h // 2 + 200),
            "\u25B6  LIKE & SUBSCRIBE",
            font_small,
            fill=config.COLOR_ACCENT_RED,
            shadow_offset=2,
            anchor="mm",
        )

        return self._save(canvas, "scene4.png")

    # ─── Helpers ────────────────────────────────────────────────────────────────

    def _dark_gradient_bg(
        self,
        top_color: tuple = (12, 12, 30),
        bottom_color: tuple = (5, 5, 12),
    ) -> Image.Image:
        """Create a vertical dark gradient background."""
        canvas = Image.new("RGB", (self.w, self.h))
        draw = ImageDraw.Draw(canvas)

        for y in range(self.h):
            ratio = y / self.h
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            draw.line([(0, y), (self.w, y)], fill=(r, g, b))

        return canvas

    def _paste_logo(
        self, canvas: Image.Image, y_pos: int = 120, size: int = 100,
    ) -> None:
        """Paste the logo centered at the given y position."""
        if not config.LOGO_FILE.exists():
            return

        try:
            logo = Image.open(config.LOGO_FILE).convert("RGBA")
            # Scale proportionally
            ratio = size / max(logo.width, logo.height)
            new_w = int(logo.width * ratio)
            new_h = int(logo.height * ratio)
            logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Center horizontally
            x = (self.w - new_w) // 2
            canvas_rgba = canvas.convert("RGBA")
            canvas_rgba.paste(logo, (x, y_pos), logo)
            canvas.paste(canvas_rgba.convert("RGB"))
        except Exception as e:
            logger.warning(f"Could not paste logo: {e}")

    def _save(self, img: Image.Image, filename: str) -> Path:
        """Save a scene frame to temp directory."""
        path = config.TEMP_DIR / filename
        img.save(str(path), "PNG")
        logger.info(f"Scene frame saved: {filename}")
        return path
