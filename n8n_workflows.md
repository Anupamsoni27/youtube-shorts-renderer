# n8n Orchestration Workflows

This document contains copy-pasteable **n8n Workflow JSONs** that you can import directly into your n8n instance to automate the entire YouTube Shorts news generation and publishing lifecycle.

---

## 1. Hourly Render & YouTube Upload Workflow

This is the main automation loop. It runs every hour on the hour, triggers the batch rendering engine, retrieves the direct Cloudflare R2 streamable videos, uploads them to YouTube, and updates MongoDB.

### How to Import This Workflow
1. Create a new empty workflow in n8n.
2. Press `Cmd + A` (Mac) or `Ctrl + A` (Windows) and delete anything there.
3. Copy the JSON below, press `Cmd + V` (Mac) or `Ctrl + V` (Windows) to paste it directly onto the n8n canvas.

```json
{
  "name": "Hourly Shorts Render & Upload",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 * * * *"
            }
          ]
        }
      },
      "id": "180373ab-a37a-4074-b901-d00742f1a6f8",
      "name": "Hourly Schedule (00:00)",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8000/batch-render",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "max_videos",
              "value": "=5"
            }
          ]
        },
        "options": {
          "timeout": 180000
        }
      },
      "id": "22ffefcb-6029-4ee7-911b-3f7d45903b70",
      "name": "Trigger Batch Render",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
    },
    {
      "parameters": {
        "fieldToSplit": "results",
        "options": {}
      },
      "id": "bc3ef88d-bf8d-4e2e-8fa9-83bc8ef07641",
      "name": "Split Render Results",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 1,
      "position": [640, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.status }}",
              "value2": "completed"
            }
          ]
        }
      },
      "id": "a98fdcb2-1da3-41bb-98bc-76cdcb328e21",
      "name": "Check If Succeeded",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2.2,
      "position": [860, 300]
    },
    {
      "parameters": {
        "url": "={{ $json.video_r2_url }}",
        "options": {
          "response": {
            "response": {
              "responseFormat": "file"
            }
          }
        }
      },
      "id": "efbc3da2-2b8d-4bb3-9da0-87efcd2a3bb1",
      "name": "Download Video Bin",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1080, 280]
    },
    {
      "parameters": {
        "title": "={{ $('Split Render Results').item.json.title }} #shorts #news",
        "description": "Daily automated news summary. #news #shorts #viral",
        "videoFile": "data",
        "options": {
          "privacyStatus": "public",
          "selfDeclaredMadeForKids": false
        }
      },
      "id": "e09dfcc1-dbcd-40a1-87ab-18df39c1b3f9",
      "name": "Upload YouTube Short",
      "type": "n8n-nodes-base.youTube",
      "typeVersion": 1,
      "position": [1300, 280],
      "credentials": {
        "youtubeOAuth2Api": {
          "id": "your_youtube_cred_id"
        }
      }
    },
    {
      "parameters": {
        "operation": "update",
        "collection": "news_records",
        "updateKey": "_id",
        "fields": {
          "fields": [
            {
              "name": "uploaded",
              "type": "boolean",
              "value": true
            },
            {
              "name": "youtubeVideoId",
              "value": "={{ $json.id }}"
            },
            {
              "name": "uploadedAt",
              "value": "={{ new Date().toISOString() }}"
            }
          ]
        }
      },
      "id": "abf12dfc-80fd-4da1-9c60-a89fdcf12314",
      "name": "Mark Uploaded in DB",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [1520, 280],
      "credentials": {
        "mongoDb": {
          "id": "your_mongodb_cred_id"
        }
      }
    }
  ],
  "connections": {
    "Hourly Schedule (00:00)": {
      "main": [
        [
          {
            "node": "Trigger Batch Render",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Trigger Batch Render": {
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
            "node": "Check If Succeeded",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Check If Succeeded": {
      "main": [
        [
          {
            "node": "Download Video Bin",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Download Video Bin": {
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
            "node": "Mark Uploaded in DB",
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

## 2. Hourly Local File Cleanup Workflow

This workflow triggers every hour at `:30` to invoke the `/cleanup` endpoint on your FastAPI server. This guarantees that temporary rendering video cache directories on your server are cleanly removed.

```json
{
  "name": "Hourly Render Cache Cleanup",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "30 * * * *"
            }
          ]
        }
      },
      "id": "e01cdfa2-581d-4054-9a8c-87dcfe987621",
      "name": "Hourly Schedule (30m)",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "method": "DELETE",
        "url": "http://localhost:8000/cleanup",
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
      "name": "Trigger Cache Cleanup",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
    }
  ],
  "connections": {
    "Hourly Schedule (30m)": {
      "main": [
        [
          {
            "node": "Trigger Cache Cleanup",
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

## 3. Stale Job Recovery Workflow

This workflow runs every hour at `:45` to recover any articles stuck in `processing` due to server power outages, process crashes, or network dropouts. It moves them back to `failed` and increments their retry counter, triggering a clean retry on the next hourly cycle.

```json
{
  "name": "Stale Job Recovery",
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
      "name": "Hourly Schedule (45m)",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8000/reset-stale",
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
      "name": "Trigger Stale Recovery",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
    }
  ],
  "connections": {
    "Hourly Schedule (45m)": {
      "main": [
        [
          {
            "node": "Trigger Stale Recovery",
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

## Configuration & Credentials Guide

### 1. MongoDB Credentials in n8n
To connect the final `Mark Uploaded in DB` node to MongoDB:
- Select the **MongoDB node** -> **Credentials**.
- Create a new connection using the **MongoDB URI** format.
- Set connection string: `mongodb+srv://anupamsoni27:Mystuff8358%401@india-01.kwer3ek.mongodb.net/`.
- Database Name: `newsapi`.

### 2. YouTube OAuth2 in n8n
To publish shorts directly onto your channel:
- Create Google Developer API credentials in the [Google Cloud Console](https://console.cloud.google.com/).
- Enable **YouTube Data API v3**.
- Set up **OAuth Consent Screen** (Web app, add redirect URL from n8n credentials panel).
- Enter Client ID and Client Secret in n8n YouTube credentials!
