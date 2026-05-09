"""
FastAPI server for the YouTube Shorts rendering pipeline.

Endpoints:
    POST   /render              — Render a video from a news article
    GET    /render-status/{id}  — Check render status for an article
    GET    /download/{slot}/{f} — Download a rendered video
    DELETE /cleanup             — Delete old output folders
    GET    /health              — Health check

    POST   /batch-render        — Fetch pending from MongoDB & render batch
    POST   /reset-stale         — Reset stuck processing jobs

Usage:
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config
from app.models import NewsArticle, NewsSource
from app.renderer import VideoRenderer
from app.utils import check_ffmpeg, ensure_fonts, setup_dirs, logger

app = FastAPI(
    title="YouTube Shorts News Video Renderer",
    description="Rendering service for automated YouTube Shorts generation",
    version="2.0.0",
)


# ─── Pydantic Models ───────────────────────────────────────────────────────────

class NewsSourceRequest(BaseModel):
    id: Optional[str] = None
    name: str = ""


class RenderRequest(BaseModel):
    """Single article render request — called by n8n or directly."""
    article_id: str = ""
    hour_slot: Optional[str] = None  # Auto-generated if not provided
    title: str = ""
    description: str = ""
    urlToImage: str = ""
    source: NewsSourceRequest = NewsSourceRequest()
    publishedAt: str = ""
    author: Optional[str] = None
    content: Optional[str] = None


class RenderResponse(BaseModel):
    status: str
    article_id: str
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    video_r2_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    render_time_seconds: Optional[float] = None
    error: Optional[str] = None
    step: Optional[str] = None


class BatchRenderRequest(BaseModel):
    """Batch render request — fetches pending articles from MongoDB."""
    max_videos: int = 5
    hour_slot: Optional[str] = None
    background: bool = True


class BatchRenderResponse(BaseModel):
    status: str
    hour_slot: str
    total_pending: int
    processed: int
    succeeded: int
    failed: int
    results: list


class CleanupRequest(BaseModel):
    older_than_hours: int = 2


class CleanupResponse(BaseModel):
    status: str
    deleted_folders: list
    freed_mb: float


class HealthResponse(BaseModel):
    status: str
    ffmpeg_available: bool
    disk_free_gb: float
    output_folders: list
    mongo_connected: bool
    r2_configured: bool


class StatusResponse(BaseModel):
    article_id: str
    status: str
    video_url: Optional[str] = None
    video_r2_url: Optional[str] = None
    file_size_mb: Optional[float] = None


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _get_hour_slot() -> str:
    """Generate current hour slot string: YYYY-MM-DD-HH"""
    return datetime.now().strftime("%Y-%m-%d-%H")


def _get_output_dir(hour_slot: str) -> Path:
    """Get or create the output directory for a given hour slot."""
    output_dir = config.OUTPUT_DIR / hour_slot
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _get_disk_free_gb() -> float:
    """Get free disk space in GB."""
    try:
        stat = shutil.disk_usage(str(config.PROJECT_ROOT))
        return round(stat.free / (1024 ** 3), 1)
    except Exception:
        return -1


# ─── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Initialize the rendering environment on server start."""
    setup_dirs()
    check_ffmpeg()
    ensure_fonts()
    from app.utils import ensure_r2_assets
    ensure_r2_assets()
    logger.info("API server v2.0 ready")


# ─── POST /render — Render a single article ─────────────────────────────────────

@app.post("/render", response_model=RenderResponse)
async def render_video(request: RenderRequest):
    """
    Render a YouTube Shorts video from a news article.
    Called by n8n Hourly Render Workflow for each article.

    - Renders synchronously (blocks until complete)
    - Saves to output/{hour_slot}/{article_id}.mp4
    - Returns download URL on success
    """
    hour_slot = request.hour_slot or _get_hour_slot()
    article_id = request.article_id or datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = _get_output_dir(hour_slot)

    # Convert to internal model
    news = NewsArticle(
        url="",
        title=request.title,
        description=request.description,
        urlToImage=request.urlToImage,
        source=NewsSource(id=request.source.id, name=request.source.name),
        publishedAt=request.publishedAt,
        author=request.author,
        content=request.content,
    )

    start = time.time()

    try:
        renderer = VideoRenderer()
        output_path = renderer.render(
            news,
            output_dir=output_dir,
            output_filename=f"{article_id}.mp4",
        )

        elapsed = time.time() - start
        file_size = output_path.stat().st_size / (1024 * 1024)

        # Upload to Cloudflare R2
        from app.r2_storage import upload_video_to_r2
        r2_url = upload_video_to_r2(output_path, hour_slot, article_id)

        return RenderResponse(
            status="completed",
            article_id=article_id,
            video_path=str(output_path),
            video_url=f"/download/{hour_slot}/{article_id}.mp4",
            video_r2_url=r2_url,
            duration_seconds=config.TOTAL_DURATION,
            file_size_mb=round(file_size, 1),
            render_time_seconds=round(elapsed, 1),
        )

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Render failed for {article_id}: {e}")
        return RenderResponse(
            status="failed",
            article_id=article_id,
            error=str(e),
            render_time_seconds=round(elapsed, 1),
        )


# ─── POST /batch-render — Fetch from MongoDB & render batch ─────────────────────

def run_batch_render_task(articles: list, hour_slot: str, output_dir: Path):
    """
    Sequence of rendering operations executed as a FastAPI background task.
    Allows n8n requests to complete instantly while rendering continues on Render.com.
    """
    from app.database import (
        mark_processing,
        mark_render_completed,
        mark_render_failed,
    )
    from app.r2_storage import upload_video_to_r2

    for article_doc in articles:
        article_id = str(article_doc["_id"])
        title = article_doc.get("title", "Untitled")

        logger.info(f"[Background Task] Starting render for article {article_id}: {title[:50]}...")

        # Mark as processing
        try:
            mark_processing(article_id, hour_slot)
        except Exception as e:
            logger.error(f"[Background Task] Failed to mark {article_id} as processing: {e}")
            continue

        # Build internal model
        source_data = article_doc.get("source", {})
        news = NewsArticle(
            url=article_doc.get("url", ""),
            title=title,
            description=article_doc.get("description", ""),
            urlToImage=article_doc.get("urlToImage", ""),
            source=NewsSource(
                id=source_data.get("id"),
                name=source_data.get("name", ""),
            ),
            publishedAt=article_doc.get("publishedAt", ""),
            author=article_doc.get("author"),
            content=article_doc.get("content"),
        )

        # Render
        start = time.time()
        try:
            renderer = VideoRenderer()
            output_path = renderer.render(
                news,
                output_dir=output_dir,
                output_filename=f"{article_id}.mp4",
            )
            elapsed = time.time() - start
            file_size = output_path.stat().st_size / (1024 * 1024)

            # Upload to Cloudflare R2
            r2_url = upload_video_to_r2(output_path, hour_slot, article_id)

            # Mark completed in MongoDB
            mark_render_completed(
                article_id=article_id,
                video_path=str(output_path),
                file_size_mb=file_size,
                render_duration=elapsed,
                video_r2_url=r2_url,
            )
            logger.info(f"[Background Task] Successfully finished rendering for article {article_id}")

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[Background Task] Failed to render {article_id}: {e}")
            try:
                mark_render_failed(article_id, str(e))
            except Exception as dbe:
                logger.error(f"[Background Task] Failed to update DB failure state for {article_id}: {dbe}")


@app.post("/batch-render", response_model=BatchRenderResponse)
async def batch_render(request: BatchRenderRequest, background_tasks: BackgroundTasks):
    """
    Fetch pending articles from MongoDB and render them.
    Supports running either synchronously or in a FastAPI background task to avoid timeouts.
    """
    from app.database import fetch_pending_articles

    hour_slot = request.hour_slot or _get_hour_slot()
    output_dir = _get_output_dir(hour_slot)

    # Fetch pending articles
    articles = fetch_pending_articles(limit=request.max_videos)

    if not articles:
        return BatchRenderResponse(
            status="completed",
            hour_slot=hour_slot,
            total_pending=0,
            processed=0,
            succeeded=0,
            failed=0,
            results=[]
        )

    if request.background:
        # Spawn the background task and return immediately!
        background_tasks.add_task(run_batch_render_task, articles, hour_slot, output_dir)
        return BatchRenderResponse(
            status="processing",
            hour_slot=hour_slot,
            total_pending=len(articles),
            processed=0,
            succeeded=0,
            failed=0,
            results=[]
        )

    # Otherwise run synchronously
    from app.database import (
        mark_processing,
        mark_render_completed,
        mark_render_failed,
    )

    results = []
    succeeded = 0
    failed = 0

    for article_doc in articles:
        article_id = str(article_doc["_id"])
        title = article_doc.get("title", "Untitled")

        logger.info(f"Processing: {title[:50]}...")

        # Mark as processing
        try:
            mark_processing(article_id, hour_slot)
        except Exception as e:
            logger.error(f"Failed to mark {article_id} as processing: {e}")
            continue

        # Build internal model
        source_data = article_doc.get("source", {})
        news = NewsArticle(
            url=article_doc.get("url", ""),
            title=title,
            description=article_doc.get("description", ""),
            urlToImage=article_doc.get("urlToImage", ""),
            source=NewsSource(
                id=source_data.get("id"),
                name=source_data.get("name", ""),
            ),
            publishedAt=article_doc.get("publishedAt", ""),
            author=article_doc.get("author"),
            content=article_doc.get("content"),
        )

        # Render
        start = time.time()
        try:
            renderer = VideoRenderer()
            output_path = renderer.render(
                news,
                output_dir=output_dir,
                output_filename=f"{article_id}.mp4",
            )
            elapsed = time.time() - start
            file_size = output_path.stat().st_size / (1024 * 1024)

            # Upload to Cloudflare R2
            from app.r2_storage import upload_video_to_r2
            r2_url = upload_video_to_r2(output_path, hour_slot, article_id)

            # Mark completed in MongoDB
            mark_render_completed(
                article_id=article_id,
                video_path=str(output_path),
                file_size_mb=file_size,
                render_duration=elapsed,
                video_r2_url=r2_url,
            )

            results.append({
                "article_id": article_id,
                "status": "completed",
                "title": title[:60],
                "video_url": f"/download/{hour_slot}/{article_id}.mp4",
                "video_r2_url": r2_url,
                "render_time": round(elapsed, 1),
            })
            succeeded += 1

        except Exception as e:
            elapsed = time.time() - start
            mark_render_failed(article_id, str(e))
            results.append({
                "article_id": article_id,
                "status": "failed",
                "title": title[:60],
                "error": str(e)[:100],
                "render_time": round(elapsed, 1),
            })
            failed += 1

    return BatchRenderResponse(
        status="completed",
        hour_slot=hour_slot,
        total_pending=len(articles),
        processed=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


# ─── GET /render-status/{article_id} ────────────────────────────────────────────

@app.get("/render-status/{article_id}", response_model=StatusResponse)
async def render_status(article_id: str):
    """
    Check if a video has been rendered for a given article.
    Searches output folders for the file.
    """
    # Search all hour-slot folders for this article's video
    for folder in sorted(config.OUTPUT_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        video_file = folder / f"{article_id}.mp4"
        if video_file.exists():
            file_size = video_file.stat().st_size / (1024 * 1024)
            return StatusResponse(
                article_id=article_id,
                status="completed",
                video_url=f"/download/{folder.name}/{article_id}.mp4",
                file_size_mb=round(file_size, 1),
            )

    return StatusResponse(
        article_id=article_id,
        status="not_found",
    )


# ─── GET /download/{hour_slot}/{filename} ────────────────────────────────────────

@app.get("/download/{hour_slot}/{filename}")
async def download_video(hour_slot: str, filename: str):
    """
    Serve a rendered video file for download.
    Used by n8n to download the video before uploading to YouTube.
    """
    video_path = config.OUTPUT_DIR / hour_slot / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {hour_slot}/{filename}")
    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=filename,
    )


# ─── DELETE /cleanup ─────────────────────────────────────────────────────────────

@app.delete("/cleanup", response_model=CleanupResponse)
async def cleanup_old_videos(request: CleanupRequest):
    """
    Delete old output folders to free disk space.
    Called by n8n Cleanup Workflow every hour at :30.

    Only deletes folders older than `older_than_hours`.
    Never deletes assets/, fonts/, or MongoDB records.
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=request.older_than_hours)
    current_slot = _get_hour_slot()

    deleted = []
    freed_bytes = 0

    if not config.OUTPUT_DIR.exists():
        return CleanupResponse(status="clean", deleted_folders=[], freed_mb=0)

    for folder in config.OUTPUT_DIR.iterdir():
        if not folder.is_dir():
            continue

        # Never delete the current hour's folder
        if folder.name == current_slot:
            continue

        # Parse folder name as datetime
        try:
            folder_time = datetime.strptime(folder.name, "%Y-%m-%d-%H")
        except ValueError:
            continue  # Skip non-hour-slot folders

        if folder_time < cutoff:
            # Calculate size before deletion
            folder_size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
            freed_bytes += folder_size

            shutil.rmtree(folder)
            deleted.append(folder.name)
            logger.info(f"Deleted output folder: {folder.name}")

    freed_mb = round(freed_bytes / (1024 * 1024), 1)
    logger.info(f"Cleanup: deleted {len(deleted)} folders, freed {freed_mb} MB")

    return CleanupResponse(
        status="cleaned",
        deleted_folders=deleted,
        freed_mb=freed_mb,
    )


# ─── POST /reset-stale ──────────────────────────────────────────────────────────

@app.post("/reset-stale")
async def reset_stale_jobs(older_than_hours: int = 2):
    """
    Reset jobs stuck in 'processing' state.
    Called by n8n Stale Job Recovery Workflow.
    """
    from app.database import reset_stale_jobs as _reset
    count = _reset(older_than_hours)
    return {
        "status": "completed",
        "reset_count": count,
    }


# ─── GET /health ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check with system status."""
    # Check MongoDB
    mongo_ok = False
    try:
        from app.database import get_collection
        get_collection()
        mongo_ok = True
    except Exception:
        pass

    # List output folders
    output_folders = []
    if config.OUTPUT_DIR.exists():
        output_folders = sorted([
            f.name for f in config.OUTPUT_DIR.iterdir() if f.is_dir()
        ])

    # Check Cloudflare R2
    from app.r2_storage import get_r2_client
    r2_configured = get_r2_client() is not None

    return HealthResponse(
        status="healthy",
        ffmpeg_available=bool(shutil.which(config.FFMPEG_BIN) or Path(config.FFMPEG_BIN).exists()),
        disk_free_gb=_get_disk_free_gb(),
        output_folders=output_folders,
        mongo_connected=mongo_ok,
        r2_configured=r2_configured,
    )


# ─── Legacy endpoint (backward compat) ──────────────────────────────────────────

@app.get("/download")
async def download_latest():
    """Download the most recently generated video (legacy)."""
    # Find the latest video across all hour slots
    if not config.OUTPUT_DIR.exists():
        raise HTTPException(status_code=404, detail="No videos found")

    for folder in sorted(config.OUTPUT_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        videos = list(folder.glob("*.mp4"))
        if videos:
            latest = max(videos, key=lambda f: f.stat().st_mtime)
            return FileResponse(str(latest), media_type="video/mp4", filename=latest.name)

    raise HTTPException(status_code=404, detail="No videos found")
