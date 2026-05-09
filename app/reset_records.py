"""
Reset all MongoDB news records back to a pristine pending state.
This is useful for re-triggering the rendering pipeline with new assets.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.database import get_collection, close_connection

def reset_database():
    col = get_collection()
    print("Connecting and resetting records...")

    # Reset both completed and failed records to pending
    result = col.update_many(
        {},
        {
            "$set": {
                "rendered": False,
                "renderStatus": "pending",
                "retryCount": 0
            },
            "$unset": {
                "videoLocalPath": "",
                "videoR2Url": "",
                "renderedAt": "",
                "processingStartedAt": "",
                "error": ""
            }
        }
    )

    print(f"Successfully reset {result.modified_count} articles back to pending!")
    close_connection()

if __name__ == "__main__":
    reset_database()
