"""
Seed MongoDB with sample news articles for testing the batch renderer.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.database import get_collection


def seed_database():
    col = get_collection()

    # Clear existing test documents if any
    print("Checking database...")

    samples = [
        {
            "url": "https://www.fool.com.au/2026/05/07/can-this-red-hot-asx-materials-stock-keep-charging-higher/",
            "author": "Aaron Bell",
            "content": "ASX materials stock Imdex Ltd (ASX: IMD) is in focus today after another big jump during yesterday's trade. It is an Australian mining equipment and technology company operating globally.",
            "description": "Is this rocketing company a buy, hold, or sell?\nThe post Can this red hot ASX materials stock keep charging higher? appeared first on The Motley Fool Australia.",
            "publishedAt": "2026-05-06T23:57:00Z",
            "source": {"id": None, "name": "Motley Fool Australia"},
            "title": "Can this red hot ASX materials stock keep charging higher?",
            "uploaded": None,
            "urlToImage": "https://www.fool.com.au/wp-content/uploads/2022/03/construction-1200x675.jpg",
        },
        {
            "url": "https://www.foxnews.com/us/repeat-offender-massive-rap-sheet-leads-cops-wild-chase-blind-passenger-begs-escape-police",
            "author": "Fox News Staff",
            "content": "A career criminal with what police say may be one of the longest rap sheets they've ever seen is back behind bars after a high-speed overnight chase Monday.",
            "description": "Police say a blind passenger begged to be let out during a high-speed stolen vehicle chase in Aurora, leading to kidnapping charges for the driver.",
            "publishedAt": "2026-05-06T23:50:00Z",
            "source": {"id": "fox-news", "name": "Fox News"},
            "title": "Repeat offender with massive rap sheet leads cops on wild chase: police",
            "uploaded": False,
            "urlToImage": "https://static.foxnews.com/foxnews.com/content/uploads/2026/05/aurora-chase-fox-news-001.gif",
        }
    ]

    print(f"Inserting {len(samples)} sample articles into {col.name}...")
    result = col.insert_many(samples)
    print(f"Successfully inserted {len(result.inserted_ids)} documents!")
    for i, inserted_id in enumerate(result.inserted_ids):
        print(f"  - Document {i+1} ID: {inserted_id}")


if __name__ == "__main__":
    seed_database()
