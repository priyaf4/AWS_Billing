# app/api/v1/

Version 1 of the ingestor API, served under `/api/v1`.

| File | Endpoint | What it does |
|---|---|---|
| `router.py` | n/a | Combines the routers below |
| `ingest.py` | `POST /api/v1/ingest` | Accepts a file and replies **202** at once; processing runs in the background |
| `documents.py` | `GET /api/v1/documents` | Every known file with its status, newest first |
| `documents.py` | `GET /api/v1/documents/{doc_id}` | One file's status (poll this to follow progress) |

## Example

```http
POST /api/v1/ingest
{ "s3_key": "uploads/1792504918425-Product_Service_Catalog_Rate_Guide.pdf" }
```
```json
202 { "doc_id": "17974f668fb669bced2f", "file_name": "Product_Service_Catalog_Rate_Guide.pdf",
      "status": "pending", ... }
```

A few seconds later, `GET /api/v1/documents/17974f668fb669bced2f`:
```json
{ "status": "ready", "page_count": 6, "chunk_count": 11, ... }
```

Status goes `pending → processing → ready`, or `→ failed` with an `error` message.

## Errors

| Status | When |
|---|---|
| `400` | `s3_key` isn't under `uploads/`, or the file type isn't supported |
| `404` | Unknown `doc_id` |
| `422` | Missing or invalid JSON body |
| `503` | DynamoDB (status table) unavailable |

Failures **during** processing don't produce an HTTP error, because the reply was already sent.
They show up as `status: "failed"` on the document.
