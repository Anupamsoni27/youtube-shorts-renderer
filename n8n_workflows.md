# n8n Orchestration Workflows — Conveyor Belt Pipeline

This document contains copy-pasteable **n8n Workflow JSONs** for the full YouTube Shorts news generation and publishing lifecycle.

---

## Architecture Overview

The pipeline uses a **Conveyor Belt** model with **6 tightly scheduled workflows**, ensuring zero overlap between rendering and uploading stages. Each hour processes up to **10 articles** (2 batches of 5).

### Hourly Timeline

```
:00  ──  Fetch News → Store articles in MongoDB (insert-if-not-exists)
:05  ──  Render Cycle 1 → Pick 5 pending articles → render in background
          ⏳ rendering... (~15-20 minutes)
:25  ──  Upload Cycle 1 → Query completed videos → upload to YouTube → delete from DB
:35  ──  Render Cycle 2 → Pick next 5 pending articles → render in background
          ⏳ rendering... (~15-20 minutes)
:45  ──  Maintenance → Reset stale jobs + clean cache
:55  ──  Upload Cycle 2 → Query completed videos → upload to YouTube → delete from DB
```

### Key Design Principles

1. **Render → Wait → Upload → Repeat**: Each render gets 20 minutes to finish before its upload cycle fires.
2. **Delete-on-upload**: Uploaded records are deleted from MongoDB so they can never be re-queried.
3. **No concurrent uploads**: n8n concurrency limit = 1 on all upload workflows.
4. **URL-based matching**: All MongoDB operations use the `url` field (not `_id`) to avoid ObjectId mismatch bugs.

---

## Workflow 1: Fetch News (at :00)

This workflow fetches news articles from an external API and stores them in MongoDB.
If you already have this workflow, simply ensure it runs at `:00` each hour.

> **Note**: The MongoDB Code Node should use the `insert-if-not-exists` pattern
> (query existing URLs first, insert only truly new articles) to avoid overwriting
> render/upload status fields on existing records.

---

## Workflow 2: Render Cycle 1 (at :05)

Triggers the FastAPI server to render up to 5 pending articles in the background.
The API returns instantly (`background=true`) while rendering continues on Render.com.

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "Render Batch — Cycle 1 (:05)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "5 * * * *"
            }
          ]
        }
      },
      "id": "180373ab-a37a-4074-b901-d00742f1a6f8",
      "name": "Every Hour at :05",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://video-shorts-renderer.onrender.com/batch-render",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "max_videos",
              "value": "=5"
            },
            {
              "name": "background",
              "value": "true"
            }
          ]
        },
        "options": {
          "timeout": 10000
        }
      },
      "id": "22ffefcb-6029-4ee7-911b-3f7d45903b70",
      "name": "Trigger Render (5 videos)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
    }
  ],
  "connections": {
    "Every Hour at :05": {
      "main": [
        [
          {
            "node": "Trigger Render (5 videos)",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## Workflow 3: Upload to YouTube — Cycle 1 (at :25)

Runs 20 minutes after Render Cycle 1 to ensure all videos have finished rendering and
are available on Cloudflare R2. Downloads each video, uploads to YouTube, and **deletes
the record from MongoDB** upon success.

#### ⚠️ Important n8n Workflow Settings:
After importing, go to **Settings (⋮ → Settings)** and set:
- **Limit Allowed Executions**: `1`
- **On Collision**: `Discard`

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "Upload to YouTube — Cycle 1 (:25)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "25 * * * *"
            }
          ]
        }
      },
      "id": "62194f95-2385-4ce2-8cd4-4d1c0848258c",
      "name": "Every Hour at :25",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [-496, 784]
    },
    {
      "parameters": {
        "collection": "news_records",
        "options": {},
        "query": "={ \"renderStatus\": \"completed\", \"uploaded\": { \"$ne\": true } }"
      },
      "id": "8b661314-b3cc-4e8a-b6f6-1ee90bc611e0",
      "name": "Query Completed & Unuploaded",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [-272, 784],
      "credentials": {
        "mongoDb": {
          "id": "7XmHhgnTAYYsPSLk",
          "name": "MongoDB account"
        }
      }
    },
    {
      "parameters": {
        "batchSize": 1,
        "options": {}
      },
      "id": "f655dca9-bb52-408d-b847-eea1ff27cb07",
      "name": "Split Render Results",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 1,
      "position": [-48, 784]
    },
    {
      "parameters": {
        "url": "={{ $json.videoR2Url }}",
        "options": {
          "response": {
            "response": {
              "responseFormat": "file"
            }
          }
        }
      },
      "id": "59531ea9-c144-4fa8-8d81-8aeb4d7e72d2",
      "name": "Download Video Bin from R2",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [176, 672]
    },
    {
      "parameters": {
        "resource": "video",
        "operation": "upload",
        "title": "={{ ($('Split Render Results').item.json.title_hi || $('Split Render Results').item.json.title).substring(0, 80) }} {{ ($('Split Render Results').item.json.viral_tags || []).join(' ') }}",
        "regionCode": "IN",
        "categoryId": "25",
        "options": {
          "description": "={{ $('Split Render Results').item.json.content_hi || $('Split Render Results').item.json.content }}",
          "privacyStatus": "public",
          "selfDeclaredMadeForKids": false
        }
      },
      "id": "518666e0-8f9f-47f8-aeed-1f9bb9de2403",
      "name": "Upload YouTube Short",
      "type": "n8n-nodes-base.youTube",
      "typeVersion": 1,
      "position": [400, 672],
      "credentials": {
        "youTubeOAuth2Api": {
          "id": "Vei7wSTOtf8pdaGd",
          "name": "YouTube account"
        }
      },
      "onError": "continueRegularOutput"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.uploadId }}",
              "operation": "isNotEmpty"
            }
          ]
        }
      },
      "id": "c72e291c-bb4a-4c31-a35f-301c05e7df24",
      "name": "Check If Upload Succeeded",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [624, 672]
    },
    {
      "parameters": {
        "operation": "delete",
        "collection": "news_records",
        "query": "={ \"url\": \"{{ $('Split Render Results').item.json.url }}\" }"
      },
      "id": "bc90a14e-106d-41ca-a3a5-36c126525986",
      "name": "Delete from DB",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [848, 592],
      "credentials": {
        "mongoDb": {
          "id": "7XmHhgnTAYYsPSLk",
          "name": "MongoDB account"
        }
      }
    }
  ],
  "connections": {
    "Every Hour at :25": {
      "main": [
        [
          {
            "node": "Query Completed & Unuploaded",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Query Completed & Unuploaded": {
      "main": [
        [
          {
            "node": "Split Render Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Split Render Results": {
      "main": [
        [
          {
            "node": "Download Video Bin from R2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Download Video Bin from R2": {
      "main": [
        [
          {
            "node": "Upload YouTube Short",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Upload YouTube Short": {
      "main": [
        [
          {
            "node": "Check If Upload Succeeded",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Check If Upload Succeeded": {
      "main": [
        [
          {
            "node": "Delete from DB",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Split Render Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Delete from DB": {
      "main": [
        [
          {
            "node": "Split Render Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## Workflow 4: Render Cycle 2 (at :35)

Identical to Workflow 2, but triggers at `:35` to pick up the next batch of 5 pending articles.

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "Render Batch — Cycle 2 (:35)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "35 * * * *"
            }
          ]
        }
      },
      "id": "a81273ab-a37a-4074-b901-d00742f1b7e9",
      "name": "Every Hour at :35",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://video-shorts-renderer.onrender.com/batch-render",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "max_videos",
              "value": "=5"
            },
            {
              "name": "background",
              "value": "true"
            }
          ]
        },
        "options": {
          "timeout": 10000
        }
      },
      "id": "b2ffefcb-6029-4ee7-911b-3f7d45903c81",
      "name": "Trigger Render (5 videos)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
    }
  ],
  "connections": {
    "Every Hour at :35": {
      "main": [
        [
          {
            "node": "Trigger Render (5 videos)",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## Workflow 5: Upload to YouTube — Cycle 2 (at :55)

Identical to Workflow 3, but triggers at `:55` to upload the second batch.

#### ⚠️ Important n8n Workflow Settings:
After importing, go to **Settings (⋮ → Settings)** and set:
- **Limit Allowed Executions**: `1`
- **On Collision**: `Discard`

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "Upload to YouTube — Cycle 2 (:55)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "55 * * * *"
            }
          ]
        }
      },
      "id": "72194f95-2385-4ce2-8cd4-4d1c0848369d",
      "name": "Every Hour at :55",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [-496, 784]
    },
    {
      "parameters": {
        "collection": "news_records",
        "options": {},
        "query": "={ \"renderStatus\": \"completed\", \"uploaded\": { \"$ne\": true } }"
      },
      "id": "9b661314-b3cc-4e8a-b6f6-1ee90bc622f1",
      "name": "Query Completed & Unuploaded",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [-272, 784],
      "credentials": {
        "mongoDb": {
          "id": "7XmHhgnTAYYsPSLk",
          "name": "MongoDB account"
        }
      }
    },
    {
      "parameters": {
        "batchSize": 1,
        "options": {}
      },
      "id": "g655dca9-bb52-408d-b847-eea1ff27dc18",
      "name": "Split Render Results",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 1,
      "position": [-48, 784]
    },
    {
      "parameters": {
        "url": "={{ $json.videoR2Url }}",
        "options": {
          "response": {
            "response": {
              "responseFormat": "file"
            }
          }
        }
      },
      "id": "69531ea9-c144-4fa8-8d81-8aeb4d7e83e3",
      "name": "Download Video Bin from R2",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [176, 672]
    },
    {
      "parameters": {
        "resource": "video",
        "operation": "upload",
        "title": "={{ ($('Split Render Results').item.json.title_hi || $('Split Render Results').item.json.title).substring(0, 80) }} {{ ($('Split Render Results').item.json.viral_tags || []).join(' ') }}",
        "regionCode": "IN",
        "categoryId": "25",
        "options": {
          "description": "={{ $('Split Render Results').item.json.content_hi || $('Split Render Results').item.json.content }}",
          "privacyStatus": "public",
          "selfDeclaredMadeForKids": false
        }
      },
      "id": "618666e0-8f9f-47f8-aeed-1f9bb9de3514",
      "name": "Upload YouTube Short",
      "type": "n8n-nodes-base.youTube",
      "typeVersion": 1,
      "position": [400, 672],
      "credentials": {
        "youTubeOAuth2Api": {
          "id": "Vei7wSTOtf8pdaGd",
          "name": "YouTube account"
        }
      },
      "onError": "continueRegularOutput"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.uploadId }}",
              "operation": "isNotEmpty"
            }
          ]
        }
      },
      "id": "d72e291c-bb4a-4c31-a35f-301c05e7ef35",
      "name": "Check If Upload Succeeded",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [624, 672]
    },
    {
      "parameters": {
        "operation": "delete",
        "collection": "news_records",
        "query": "={ \"url\": \"{{ $('Split Render Results').item.json.url }}\" }"
      },
      "id": "cc90a14e-106d-41ca-a3a5-36c126536097",
      "name": "Delete from DB",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [848, 592],
      "credentials": {
        "mongoDb": {
          "id": "7XmHhgnTAYYsPSLk",
          "name": "MongoDB account"
        }
      }
    }
  ],
  "connections": {
    "Every Hour at :55": {
      "main": [
        [
          {
            "node": "Query Completed & Unuploaded",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Query Completed & Unuploaded": {
      "main": [
        [
          {
            "node": "Split Render Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Split Render Results": {
      "main": [
        [
          {
            "node": "Download Video Bin from R2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Download Video Bin from R2": {
      "main": [
        [
          {
            "node": "Upload YouTube Short",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Upload YouTube Short": {
      "main": [
        [
          {
            "node": "Check If Upload Succeeded",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Check If Upload Succeeded": {
      "main": [
        [
          {
            "node": "Delete from DB",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Split Render Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Delete from DB": {
      "main": [
        [
          {
            "node": "Split Render Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## Workflow 6: Maintenance — Stale Recovery + Cleanup (at :45)

Combined maintenance workflow that resets stuck rendering jobs and cleans up old
local video cache files. Runs once per hour between the two render+upload cycles.

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "Maintenance: Stale Recovery + Cleanup (:45)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "45 * * * *"
            }
          ]
        }
      },
      "id": "981273ab-28fa-4e89-10df-871abfdc12ef",
      "name": "Every Hour at :45",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://video-shorts-renderer.onrender.com/reset-stale",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "older_than_hours",
              "value": "=2"
            }
          ]
        }
      },
      "id": "ef23abf1-2cd0-4dbf-87eb-10fcdbf123a1",
      "name": "Reset Stale Jobs",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
    },
    {
      "parameters": {
        "method": "DELETE",
        "url": "https://video-shorts-renderer.onrender.com/cleanup",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "older_than_hours",
              "value": "=2"
            }
          ]
        }
      },
      "id": "18acbe3d-3dfd-4a12-87dc-fc394d12ebcd",
      "name": "Cleanup Cache",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [640, 300]
    }
  ],
  "connections": {
    "Every Hour at :45": {
      "main": [
        [
          {
            "node": "Reset Stale Jobs",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Reset Stale Jobs": {
      "main": [
        [
          {
            "node": "Cleanup Cache",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## n8n Settings Checklist

After importing all workflows, apply these settings:

### Upload Workflows (Cycle 1 and Cycle 2):
1. Open the workflow → Click **⋮ (three dots)** → **Settings**
2. Set **Limit Allowed Executions** to `1`
3. Set **On Collision** to `Discard`
4. Save

This prevents any possibility of overlapping upload runs.

---

## Configuration & Credentials Guide

### 1. MongoDB Credentials in n8n
- Select the **MongoDB node** → **Credentials**.
- Create a new connection using the **MongoDB URI** format.
- Set connection string: `mongodb+srv://anupamsoni27:Mystuff8358%401@india-01.kwer3ek.mongodb.net/`.
- Database Name: `newsapi`.

### 2. YouTube OAuth2 in n8n
- Create Google Developer API credentials in the [Google Cloud Console](https://console.cloud.google.com/).
- Enable **YouTube Data API v3**.
- Set up **OAuth Consent Screen** (Web app, add redirect URL from n8n credentials panel).
- Enter Client ID and Client Secret in n8n YouTube credentials!
