"""
FFmpeg command builder for the video rendering pipeline.
Constructs and executes FFmpeg commands for:
  - Scene animation (zoompan on static PNGs)
  - Scene concatenation with crossfade transitions
  - Background video compositing
  - Background music mixing

All FFmpeg calls use config.FFMPEG_BIN which auto-detects the binary path.
"""

from pathlib import Path

from app import config
from app.utils import logger, run_ffmpeg


class FFmpegBuilder:
    """Builds and executes the FFmpeg rendering pipeline."""

    def __init__(self):
        self.w = config.VIDEO_WIDTH
        self.h = config.VIDEO_HEIGHT
        self.fps = config.FPS
        self.ffmpeg = config.FFMPEG_BIN
        self.scene_durations = [
            config.SCENE_1_DURATION,
            config.SCENE_2_DURATION,
            config.SCENE_3_DURATION,
            config.SCENE_4_DURATION,
        ]
        self.xfade_dur = config.XFADE_DURATION

    # ─── Step 1: Animate each scene PNG with zoompan ────────────────────────────

    def animate_scenes(self, scene_pngs: list) -> list:
        """
        Convert static scene PNGs into animated MP4 segments using zoompan.
        Each scene gets a unique zoom/pan effect for visual interest.
        """
        scene_videos = []

        zoom_configs = [
            # Scene 1: Slight zoom in + fade in from black
            {
                "zoom": "min(zoom+0.0009,1.08)",
                "x": "iw/2-(iw/zoom/2)",
                "y": "ih/2-(ih/zoom/2)",
                "extras": ",fade=t=in:st=0:d=0.8:color=black",
            },
            # Scene 2: Slow Ken Burns zoom (cinematic)
            {
                "zoom": "min(zoom+0.0004,1.12)",
                "x": "iw/2-(iw/zoom/2)",
                "y": "ih/2-(ih/zoom/2)",
                "extras": "",
            },
            # Scene 3: Subtle zoom with slight horizontal drift
            {
                "zoom": "min(zoom+0.0005,1.08)",
                "x": "iw/2-(iw/zoom/2)",
                "y": "ih/2-(ih/zoom/2)",
                "extras": "",
            },
            # Scene 4: Gentle zoom + fade out to black
            {
                "zoom": "min(zoom+0.0006,1.06)",
                "x": "iw/2-(iw/zoom/2)",
                "y": "ih/2-(ih/zoom/2)",
                "extras": f",fade=t=out:st={self.scene_durations[3]-1.5}:d=1.5:color=black",
            },
        ]

        for i, (png_path, duration) in enumerate(zip(scene_pngs, self.scene_durations)):
            output_path = config.TEMP_DIR / f"scene{i+1}.mp4"
            frames = duration * self.fps
            zcfg = zoom_configs[i]

            zoompan = (
                f"zoompan="
                f"z='{zcfg['zoom']}':"
                f"x='{zcfg['x']}':"
                f"y='{zcfg['y']}':"
                f"d={frames}:"
                f"s={self.w}x{self.h}:"
                f"fps={self.fps}"
                f"{zcfg['extras']}"
            )

            cmd = [
                self.ffmpeg, "-y",
                "-i", str(png_path),
                "-vf", zoompan,
                "-c:v", config.CODEC,
                "-preset", config.PRESET,
                "-crf", str(config.CRF),
                "-pix_fmt", config.PIXEL_FORMAT,
                "-t", str(duration),
                str(output_path),
            ]

            success = run_ffmpeg(cmd, f"Animate scene {i+1} ({duration}s)")
            if not success:
                raise RuntimeError(f"Failed to animate scene {i+1}")

            scene_videos.append(output_path)

        return scene_videos

    # ─── Step 2: Concatenate scenes with crossfade transitions ──────────────────

    def concatenate_scenes(self, scene_videos: list) -> Path:
        """
        Concatenate scene videos with xfade crossfade transitions.
        Uses FFmpeg's xfade filter for smooth transitions between scenes.
        """
        output_path = config.TEMP_DIR / "concat.mp4"

        # Build input args
        inputs = []
        for vid in scene_videos:
            inputs.extend(["-i", str(vid)])

        # Build xfade filter chain
        # Each xfade takes two inputs and produces one output
        # Offsets must account for previous xfade overlaps
        filter_parts = []
        accumulated_duration = self.scene_durations[0]

        for i in range(1, len(scene_videos)):
            offset = accumulated_duration - self.xfade_dur
            in_label = f"[{i-1}:v]" if i == 1 else f"[v{i-1}]"
            out_label = f"[v{i}]" if i < len(scene_videos) - 1 else "[vout]"

            filter_parts.append(
                f"{in_label}[{i}:v]xfade=transition=fade:"
                f"duration={self.xfade_dur}:offset={offset}{out_label}"
            )
            accumulated_duration += self.scene_durations[i] - self.xfade_dur

        filter_complex = ";".join(filter_parts)

        cmd = [
            self.ffmpeg, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", config.CODEC,
            "-preset", config.PRESET,
            "-crf", str(config.CRF),
            "-pix_fmt", config.PIXEL_FORMAT,
            str(output_path),
        ]

        success = run_ffmpeg(cmd, "Concatenate scenes with crossfade")
        if not success:
            raise RuntimeError("Failed to concatenate scenes")

        return output_path

    # ─── Step 3: Composite with background video ───────────────────────────────

    def composite_with_background(self, scene_video: Path) -> Path:
        """
        Blend the scene video with the looping background video.
        Background is darkened and the scene video is overlaid at high opacity.
        Falls back to scene-only if bg.mp4 is missing.
        """
        output_path = config.TEMP_DIR / "composed.mp4"

        if not config.BG_VIDEO.exists():
            logger.warning("bg.mp4 not found — skipping background composite")
            import shutil
            shutil.copy2(scene_video, output_path)
            return output_path

        # Get the duration of the concatenated video
        total_dur = config.TOTAL_DURATION

        # NOTE: Background compositing via blend filter is disabled because:
        #   - Placeholder bg.mp4 (solid dark) adds no visual value
        #   - Scene PNGs already have designed dark gradient backgrounds
        #   - blend filter causes color issues (pink tint / blackout)
        # To re-enable with a real bg.mp4, use overlay filter with alpha.
        # For now, just pass the scene video through directly.
        import shutil
        logger.info("Using scene video directly (bg composite disabled)")
        shutil.copy2(scene_video, output_path)
        return output_path

        # ── Reserved: future bg composite with proper overlay ──
        # filter_complex = (
        #     f"[0:v]loop=loop=-1:size={self.fps * 30}:start=0,"
        #     f"trim=0:{total_dur},setpts=PTS-STARTPTS,"
        #     f"scale={self.w}:{self.h},setsar=1,"
        #     f"eq=brightness=-0.5:saturation=0.3[bg];"
        #     f"[1:v]format=yuva420p,colorchannelmixer=aa=0.92[scene];"
        #     f"[bg][scene]overlay=0:0[vout]"
        # )

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(config.BG_VIDEO),
            "-i", str(scene_video),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", config.CODEC,
            "-preset", config.PRESET,
            "-crf", str(config.CRF),
            "-pix_fmt", config.PIXEL_FORMAT,
            "-t", str(total_dur),
            str(output_path),
        ]

        success = run_ffmpeg(cmd, "Composite with background")
        if not success:
            logger.warning("Background composite failed — using scene video only")
            import shutil
            shutil.copy2(scene_video, output_path)

        return output_path

    # ─── Step 4: Add background music ───────────────────────────────────────────

    def add_music(self, video_path: Path, output_path: Path = None) -> Path:
        """
        Add background music to the video.
        Music is trimmed/looped to match video duration with fade-out.
        """
        if output_path is None:
            output_path = config.OUTPUT_DIR / "final_video.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_dur = config.TOTAL_DURATION

        if not config.MUSIC_FILE.exists():
            logger.warning("music.mp3 not found — rendering without music")
            import shutil
            shutil.copy2(video_path, output_path)
            return output_path

        # Audio filter: loop if needed, trim, fade in/out
        audio_filter = (
            f"afade=t=in:st=0:d=1,"
            f"afade=t=out:st={total_dur - 2}:d=2,"
            f"atrim=0:{total_dur},"
            f"asetpts=PTS-STARTPTS,"
            f"volume=0.3"
        )

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1",
            "-i", str(config.MUSIC_FILE),
            "-filter_complex", f"[1:a]{audio_filter}[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",  # No re-encode for video
            "-c:a", config.AUDIO_CODEC,
            "-b:a", config.AUDIO_BITRATE,
            "-t", str(total_dur),
            "-shortest",
            str(output_path),
        ]

        success = run_ffmpeg(cmd, "Add background music")
        if not success:
            logger.warning("Music mixing failed — rendering without music")
            import shutil
            shutil.copy2(video_path, output_path)

        return output_path
