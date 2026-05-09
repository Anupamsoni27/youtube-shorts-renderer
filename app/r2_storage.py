"""
Cloudflare R2 storage manager.
Handles uploading generated videos to Cloudflare R2 using the boto3 S3-compatible API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.client import Config
from dotenv import load_dotenv

from app.utils import logger

load_dotenv()


def get_r2_client() -> Optional[boto3.client]:
    """
    Configure and return a Cloudflare R2 S3 client if credentials are set.
    Returns None if R2 is not fully configured.
    """
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("R2_BUCKET_NAME")

    # Guard clause to check if placeholder credentials are still present
    if not all([account_id, access_key, secret_key, bucket_name]):
        return None

    if "your_" in account_id or "your_" in access_key or "your_" in secret_key:
        return None

    try:
        # Cloudflare R2 endpoint URL structure
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        return s3_client
    except Exception as e:
        logger.error(f"Failed to initialize Cloudflare R2 client: {e}")
        return None


def upload_video_to_r2(file_path: Path, hour_slot: str, article_id: str) -> Optional[str]:
    """
    Upload a rendered video to Cloudflare R2.
    
    Args:
        file_path: Path to the local MP4 file.
        hour_slot: The hour folder name (e.g. '2026-05-09-16').
        article_id: MongoDB ID or filename.
        
    Returns:
        The public access URL for the uploaded video, or None if R2 isn't configured/upload fails.
    """
    s3_client = get_r2_client()
    if s3_client is None:
        logger.info("Cloudflare R2 is not configured — skipping R2 upload (using local download links)")
        return None

    bucket_name = os.getenv("R2_BUCKET_NAME")
    public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

    # Object key structure: e.g. '2026-05-09-16/69ff16eb5d7bd6109a19b219.mp4'
    object_key = f"{hour_slot}/{article_id}.mp4"

    logger.info(f"Uploading video {file_path.name} to Cloudflare R2 bucket: {bucket_name}")
    try:
        s3_client.upload_file(
            Filename=str(file_path),
            Bucket=bucket_name,
            Key=object_key,
            ExtraArgs={
                "ContentType": "video/mp4"
            }
        )
        
        # Build public URL
        if public_url:
            video_url = f"{public_url}/{object_key}"
        else:
            # Fallback to dev subdomain endpoint if custom domain is not set
            account_id = os.getenv("R2_ACCOUNT_ID")
            video_url = f"https://{bucket_name}.{account_id}.r2.cloudflarestorage.com/{object_key}"
            
        logger.info(f"Video uploaded to R2 successfully: {video_url}")
        return video_url

    except Exception as e:
        logger.error(f"Cloudflare R2 upload failed: {e}")
        return None
