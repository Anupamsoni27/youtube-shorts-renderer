# YouTube Shorts News Video Generator

Automated video generation system that converts news articles into YouTube Shorts-optimized vertical videos (1080×1920) using FFmpeg and Python. Linked to MongoDB for article scheduling and Cloudflare R2 for cloud storage.

## Features

- 🎬 Generates **1080×1920 vertical MP4** videos optimized for YouTube Shorts
- 🔄 **MongoDB State Machine**: Tracks article rendering pipeline status (`pending`, `processing`, `completed`, `failed`)
- ☁️ **Cloudflare R2 Storage**: Automatically uploads rendered videos to Cloudflare R2 bucket with clean public URLs
- ⏰ **Hourly Automation Ready**: Structured with sequential batch rendering (`/batch-render`) and auto-cleanup (`/cleanup`) to maintain zero disk leakage
- 🖼️ Downloads and processes news images (GIF, JPG, PNG support)
- 📐 Intelligent blur-fill background for non-standard aspect ratios
- 🎨 Professional scene transitions with Ken Burns zoom effects
- 🎵 Background music with auto-trim and fade
- 🌐 FastAPI endpoints for orchestration (n8n, webhooks, Cron triggers, etc.)

## Tech Stack

- **Python 3.12**
- **MongoDB Atlas** — State machine and article scheduling
- **Cloudflare R2 (S3 API)** — Public video file storage
- **FFmpeg** (via subprocess — no MoviePy dependency)
- **Pillow** — image processing and scene frame generation
- **FastAPI** — REST API with batch and lifecycle endpoints
- **boto3** — Cloudflare R2 uploads

---

## Configuration & Environment Setup

Copy or edit the `.env` file in the project root to configure connections:

```ini
# ─── MongoDB ───
MONGO_URI=mongodb+srv://<username>:<password>@india-01.kwer3ek.mongodb.net/
MONGO_DB=newsapi
MONGO_COLLECTION=news_records

# ─── Cloudflare R2 Storage ───
# Obtain these in Cloudflare Dashboard -> R2 -> Manage R2 API Tokens
R2_ACCOUNT_ID=your_cloudflare_account_id_here
R2_ACCESS_KEY_ID=your_r2_access_key_id_here
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key_here
R2_BUCKET_NAME=your_r2_bucket_name_here
R2_PUBLIC_URL=https://pub-yourbucketid.r2.dev

# ─── Rendering & Server Limits ───
MAX_VIDEOS_PER_HOUR=5
CLEANUP_AFTER_HOURS=2
MAX_RETRY_COUNT=3
PORT=8000
```

---

## Prerequisites

### FFmpeg (Required)

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Verify installation
ffmpeg -version
```

### Python 3.12+

```bash
python3 --version
```

---

## Quick Start

### 1. Setup Virtual Environment & Dependencies

```bash
cd video_renderer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Seed Database with Test Documents (MongoDB)

```bash
python app/seed_db.py
```

### 3. Run FastAPI v2 Server Locally

```bash
uvicorn api.server:app --reload --port 8000
```

---

## API Endpoints for n8n Automation

### 1. Health & Configuration Discovery
- **Endpoint**: `GET /health`
- **Returns**: Status of FFmpeg, free disk space, MongoDB connectivity, and Cloudflare R2 configuration status (`r2_configured: true/false`).

### 2. Batch Render (The Core Hourly automation)
- **Endpoint**: `POST /batch-render`
- **Payload**:
```json
{
    "max_videos": 5
}
```
- **Action**:
  1. Automatically queries MongoDB for pending articles.
  2. Sets state to `processing` in DB to prevent duplicate jobs.
  3. Sequentially renders video outputs.
  4. Uploads final files to **Cloudflare R2** under `YYYY-MM-DD-HH/{article_id}.mp4` key.
  5. Updates MongoDB with `rendered: true`, `videoR2Url`, `renderedAt`, and runtime statistics.

### 3. Automatic Cleanup
- **Endpoint**: `DELETE /cleanup`
- **Payload**:
```json
{
    "older_than_hours": 2
}
```
- **Action**: Clears out local cache output folders older than 2 hours to keep local disk usage light.

---

## Core Directory Structure

```
video_renderer/
├── .env                    ← Connections & Storage limits (MongoDB / Cloudflare R2)
├── .gitignore              ← Excludes credentials, cache, virtualenvs, outputs
├── app/
│   ├── config.py           ← Video parameters, paths, colors
│   ├── database.py         ← MongoDB state machine queries and updates
│   ├── r2_storage.py       ← Cloudflare R2 file uploader (boto3)
│   ├── seed_db.py          ← Database seeding helper for tests
│   ├── image_processor.py  ← Image retrieval, resize, blur-fill
│   ├── scene_builder.py    ← Pillow scene frame generation
│   ├── ffmpeg_builder.py   ← Ken Burns zoompan & audio merging
│   ├── renderer.py         ← Orchestrates step-by-step video rendering
│   └── utils.py            ← Text wrapping, fonts, logging
├── api/
│   └── server.py           ← Full FastAPI v2 server and REST endpoints
├── requirements.txt        ← Python requirements
└── README.md
```

## Video Specs

| Property | Value |
|----------|-------|
| Resolution | 1080 × 1920 (9:16) |
| Codec | H.264 (libx264) |
| Frame Rate | 30 FPS |
| Duration | ~23.5 seconds |
| Audio | AAC 128kbps |
| Pixel Format | yuv420p |

## Future Roadmap

- [ ] MongoDB integration for news articles
- [ ] AI voice generation (text-to-speech)
- [ ] Subtitle overlay
- [ ] Multiple video templates
- [ ] n8n workflow integration
- [ ] Auto-upload to YouTube via API
- [ ] Batch rendering queue

## License

Private project — all rights reserved.
