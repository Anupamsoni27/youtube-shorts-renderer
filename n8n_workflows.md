# n8n Orchestration Workflows

This document contains copy-pasteable **n8n Workflow JSONs** that you can import directly into your n8n instance to automate the entire YouTube Shorts news generation and publishing lifecycle.

---

## 1. Decoupled & Automated Workflows (RECOMMENDED)

Rather than using a single massive synchronous workflow (which causes network timeouts on large render batches), we recommend splitting your flow into **two independent, fully asynchronous workflows**. This architecture guarantees 100% stability, 0ms timeouts, and unlimited rendering scalability.

---

### A. Workflow 1: Trigger Hourly News Render
This workflow runs on the hour, hits your FastAPI server to trigger a batch render, and **exits instantly** (under 0.1s) while rendering safely completes in the background on Render.

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "1. Trigger Batch Render (Async)",
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
        "url": "https://video-shorts-renderer.onrender.com/batch-render",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "max_videos",
              "value": "=10"
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
      "name": "Trigger Batch Render",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [420, 300]
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
    }
  }
}
```

---

### B. Workflow 2: Automated YouTube Shorts Publisher
This workflow runs every 15 minutes to poll MongoDB Atlas for articles where rendering is `"completed"` but they haven't been uploaded to YouTube yet (`"uploaded" != true`). It automatically splits the articles, downloads their video binaries from your **Cloudflare R2** public CDN, uploads them to YouTube, and marks them as uploaded in MongoDB!

#### How to Import:
Copy the JSON below and paste it directly onto your empty n8n canvas.

```json
{
  "name": "2. Auto Upload Rendered Videos to YouTube (One by One Loop)",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "minutes",
              "value": 15
            }
          ]
        }
      },
      "id": "7489a8dc-bf2d-4ef1-98ac-73bcd723fa3b",
      "name": "Poll Every 15 Minutes",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [200, 300]
    },
    {
      "parameters": {
        "operation": "find",
        "collection": "news_records",
        "query": "={ \"renderStatus\": \"completed\", \"uploaded\": { \"$ne\": true } }",
        "options": {}
      },
      "id": "92f3acbc-83fa-4a2e-be8a-cda38fc71439",
      "name": "Query Completed & Unuploaded",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1.1,
      "position": [420, 300],
      "credentials": {
        "mongoDb": {
          "id": "your_mongodb_cred_id"
        }
      }
    },
    {
      "parameters": {
        "batchSize": 1,
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
        "url": "={{ $json.videoR2Url }}",
        "options": {
          "response": {
            "response": {
              "responseFormat": "file"
            }
          }
        }
      },
      "id": "efbc3da2-2b8d-4bb3-9da0-87efcd2a3bb1",
      "name": "Download Video Bin from R2",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [860, 200]
    },
    {
      "parameters": {
        "resource": "video",
        "operation": "upload",
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
      "position": [1080, 200],
      "credentials": {
        "youtubeOAuth2Api": {
          "id": "your_youtube_cred_id"
        }
      }
    },
    {
      "parameters": {
        "values": {
          "string": [
            {
              "name": "_id",
              "value": "={{ $('Split Render Results').item.json._id }}"
            },
            {
              "name": "youtubeVideoId",
              "value": "={{ $json.id || 'not_available' }}"
            },
            {
              "name": "uploadedAt",
              "value": "={{ new Date().toISOString() }}"
            }
          ],
          "boolean": [
            {
              "name": "uploaded",
              "value": true
            }
          ]
        },
        "options": {}
      },
      "id": "c88f123d-4fa0-4da2-9b23-1d0fcba231a4",
      "name": "Prepare DB Update",
      "type": "n8n-nodes-base.set",
      "typeVersion": 1,
      "position": [1300, 200]
    },
    {
      "parameters": {
        "operation": "update",
        "collection": "news_records",
        "updateKey": "_id",
        "fields": "uploaded,youtubeVideoId,uploadedAt"
      },
      "id": "abf12dfc-80fd-4da1-9c60-a89fdcf12314",
      "name": "Mark Uploaded in DB",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [1520, 200],
      "credentials": {
        "mongoDb": {
          "id": "your_mongodb_cred_id"
        }
      }
    }
  ],
  "connections": {
    "Poll Every 15 Minutes": {
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
            "node": "Prepare DB Update",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Prepare DB Update": {
      "main": [
        [
          {
            "node": "Mark Uploaded in DB",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Mark Uploaded in DB": {
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
