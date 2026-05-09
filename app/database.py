"""
MongoDB connection manager.
Handles connection pooling, queries, and state updates for news articles.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.utils import logger

# Load environment variables
load_dotenv()

# ─── Connection ─────────────────────────────────────────────────────────────────

_client: Optional[MongoClient] = None
_db: Optional[Database] = None
_collection: Optional[Collection] = None


def get_collection() -> Collection:
    """
    Get the MongoDB collection, creating the connection if needed.
    Connection is cached (singleton) for the lifetime of the process.
    """
    global _client, _db, _collection

    if _collection is not None:
        return _collection

    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGO_DB", "newsapi")
    mongo_col = os.getenv("MONGO_COLLECTION", "news_records")

    if not mongo_uri:
        raise RuntimeError("MONGO_URI not set in environment / .env file")

    logger.info(f"Connecting to MongoDB: {mongo_db}.{mongo_col}")
    _client = MongoClient(mongo_uri)
    _db = _client[mongo_db]
    _collection = _db[mongo_col]

    # Verify connection
    _client.admin.command("ping")
    logger.info("MongoDB connected successfully")

    return _collection


def close_connection() -> None:
    """Close the MongoDB connection."""
    global _client, _db, _collection
    if _client:
        _client.close()
        _client = None
        _db = None
        _collection = None
        logger.info("MongoDB connection closed")


# ─── Queries ────────────────────────────────────────────────────────────────────

def fetch_pending_articles(limit: int = 5) -> list:
    """
    Fetch articles that need rendering.
    Filters: rendered=false, not currently processing, retryCount < max.
    Sorted by publishedAt descending (newest first).
    """
    col = get_collection()
    max_retries = int(os.getenv("MAX_RETRY_COUNT", "3"))

    query = {
        "$or": [
            {"rendered": False},
            {"rendered": {"$exists": False}},
        ],
        "renderStatus": {"$nin": ["processing", "completed"]},
        "$or": [
            {"retryCount": {"$exists": False}},
            {"retryCount": {"$lt": max_retries}},
        ],
    }

    # Fix $or conflict — use $and to combine both $or conditions
    query = {
        "$and": [
            {
                "$or": [
                    {"rendered": False},
                    {"rendered": {"$exists": False}},
                ]
            },
            {
                "$or": [
                    {"uploaded": False},
                    {"uploaded": {"$exists": False}},
                    {"uploaded": None},
                ]
            },
            {
                "renderStatus": {"$nin": ["processing", "completed"]}
            },
            {
                "$or": [
                    {"retryCount": {"$exists": False}},
                    {"retryCount": {"$lt": max_retries}},
                ]
            },
        ]
    }

    articles = list(
        col.find(query)
        .sort("publishedAt", -1)
        .limit(limit)
    )

    logger.info(f"Found {len(articles)} pending articles (limit={limit})")
    return articles


# ─── State Updates ──────────────────────────────────────────────────────────────

def mark_processing(article_id: str, hour_slot: str) -> None:
    """Mark an article as currently being rendered."""
    col = get_collection()
    from bson import ObjectId

    col.update_one(
        {"_id": ObjectId(article_id)},
        {
            "$set": {
                "renderStatus": "processing",
                "processingStartedAt": datetime.now(timezone.utc),
                "hourSlot": hour_slot,
            }
        },
    )
    logger.info(f"Article {article_id}: marked as processing")


def mark_render_completed(
    article_id: str,
    video_path: str,
    file_size_mb: float,
    render_duration: float,
    video_r2_url: Optional[str] = None,
) -> None:
    """Mark an article as successfully rendered."""
    col = get_collection()
    from bson import ObjectId

    update_doc = {
        "rendered": True,
        "renderStatus": "completed",
        "renderedAt": datetime.now(timezone.utc),
        "videoLocalPath": video_path,
        "fileSizeMb": round(file_size_mb, 2),
        "renderDurationSeconds": round(render_duration, 1),
    }

    if video_r2_url:
        update_doc["videoR2Url"] = video_r2_url

    col.update_one(
        {"_id": ObjectId(article_id)},
        {
            "$set": update_doc
        },
    )
    logger.info(f"Article {article_id}: render completed")


def mark_render_failed(article_id: str, error: str) -> None:
    """Mark an article render as failed and increment retry count."""
    col = get_collection()
    from bson import ObjectId

    col.update_one(
        {"_id": ObjectId(article_id)},
        {
            "$set": {
                "renderStatus": "failed",
                "renderError": error,
            },
            "$inc": {
                "retryCount": 1,
            },
        },
    )
    logger.info(f"Article {article_id}: render failed — {error[:60]}")


def mark_uploaded(
    article_id: str,
    youtube_url: str,
    youtube_video_id: str,
) -> None:
    """Mark an article as uploaded to YouTube."""
    col = get_collection()
    from bson import ObjectId

    col.update_one(
        {"_id": ObjectId(article_id)},
        {
            "$set": {
                "uploaded": True,
                "uploadStatus": "completed",
                "youtubeUrl": youtube_url,
                "youtubeVideoId": youtube_video_id,
                "uploadedAt": datetime.now(timezone.utc),
            }
        },
    )
    logger.info(f"Article {article_id}: uploaded to YouTube")


def reset_stale_jobs(older_than_hours: int = 2) -> int:
    """Reset jobs stuck in 'processing' state for too long."""
    col = get_collection()
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)

    result = col.update_many(
        {
            "renderStatus": "processing",
            "processingStartedAt": {"$lt": cutoff},
        },
        {
            "$set": {
                "renderStatus": "failed",
                "renderError": f"Timed out after {older_than_hours} hours",
            },
            "$inc": {
                "retryCount": 1,
            },
        },
    )

    if result.modified_count > 0:
        logger.info(f"Reset {result.modified_count} stale jobs")
    return result.modified_count
