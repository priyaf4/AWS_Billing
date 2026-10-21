# app/

All the ingestor's Python code, as one package (`from app.pipeline.chunker import chunk_pages`).

## main.py

Creates the FastAPI app, mounts the routes under `/api/v1`, and defines `GET /health`.
`uvicorn app.main:app` serves it.

## Sub-folders, in the order a request travels

| Folder | Role |
|---|---|
| `api/` | Receives HTTP requests, starts background work, returns responses |
| `schemas/` | What valid requests and responses look like |
| `pipeline/` | The RAG steps: load → chunk → embed, and `pipeline.py`, which runs them |
| `infra/` | Talks to AWS: S3, OpenSearch, DynamoDB |
| `core/` | Settings and the shared AWS session |

**Rule of thumb:** routes stay thin, the steps live in `pipeline/`, and only `infra/` (plus the embedder) knows about AWS.

## Why the code is synchronous (`def`, not `async def`)

Every step is blocking I/O (boto3, OpenSearch) or CPU work (PDF parsing). FastAPI runs plain `def` routes and
background tasks in a thread pool automatically, so synchronous code is simpler here and still doesn't block the server.
