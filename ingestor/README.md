# RAG Ingestor

A separate microservice that turns files uploaded on the **Filestorage** page into searchable knowledge for the chat.
It reads each file from S3, splits it into chunks, turns every chunk into a vector with Amazon Titan, and stores them in OpenSearch.

It runs on its own (own dependencies, venv and port), so it can be deployed and scaled separately from the chat backend.

## Big picture

```
Filestorage page ── upload ──► S3 (uploads/)
        │
        └── POST /api/v1/ingest {s3_key} ──► INGESTOR (this folder)
                                               │  replies 202 "pending" right away, then in the background:
                                               │   1. download the file from S3           infra/s3.py
                                               │   2. extract text, page by page          pipeline/loader.py
                                               │   3. split into overlapping chunks       pipeline/chunker.py
                                               │   4. embed each chunk (Bedrock Titan V2) pipeline/embedder.py
                                               │   5. write chunks + vectors              infra/vector_store.py ──► OpenSearch "kb-chunks"
                                               │   6. record status at every step         infra/documents_repo.py ─► DynamoDB "documents"
                                               ▼
        Filestorage page polls GET /api/v1/documents and shows: Indexing... → Ready (11 chunks) / Failed
```

The chat backend will later **read** from the same OpenSearch index (see "Contract with the chat backend").
The two services never call each other.

## Folder map

```
ingestor/
├── app/
│   ├── main.py           starts the app, registers routes        → app/README.md
│   ├── api/              HTTP layer                               → app/api/README.md
│   │   └── v1/           POST /ingest, GET /documents             → app/api/v1/README.md
│   ├── pipeline/         the RAG steps: load, chunk, embed, run   → app/pipeline/README.md
│   ├── infra/            S3, OpenSearch, DynamoDB                 → app/infra/README.md
│   ├── schemas/          request/response shapes                  → app/schemas/README.md
│   └── core/             settings, AWS session                    → app/core/README.md
├── scripts/              one-off admin and check scripts          → scripts/README.md
├── tests/                automated tests (no AWS calls)           → tests/README.md
├── pyproject.toml        project info + dependencies
├── .env.example          template for settings and keys
└── .env                  your real settings (never commit this)
```

## Run locally

```powershell
cd ingestor
python -m venv .venv                       # one time
.venv\Scripts\activate
pip install -e ".[dev]"                    # install dependencies from pyproject.toml
copy .env.example .env                     # one time: then add the rag-ingestor-user keys

.venv\Scripts\python -m uvicorn app.main:app --reload --port 8002
```

- API docs: http://localhost:8002/docs
- Health: http://localhost:8002/health
- Tests: `pytest`

Ports: chat backend 8000, ingestor **8002**, frontend 3000. The frontend finds the ingestor through `INGESTOR_URL` (default `http://localhost:8002`).

## AWS resources it uses

| Resource | Name | Access (IAM user `rag-ingestor-user`) |
|---|---|---|
| S3 bucket | `priya-genai-rag-docs-2026`, prefix `uploads/` | Read files |
| Bedrock model | `amazon.titan-embed-text-v2:0` | Create embeddings |
| OpenSearch domain | `rag-opensearch-poc`, index `kb-chunks` | OpenSearch role `rag_ingestor` (see `scripts/`) |
| DynamoDB table | `documents` | Read/write file status |

Check them all at any time with `python scripts/check_access.py`.

## Behaviour worth knowing

| Situation | What happens |
|---|---|
| Same file name uploaded again | Same `doc_id`, so its chunks are **replaced**, not duplicated. The older S3 copy shows as "Older copy". |
| Scanned PDF (images only) | Status `failed`: "No text found" (needs OCR, which isn't supported yet) |
| Unsupported type (e.g. `.jpg`) | Rejected immediately with `400` |
| File over `MAX_FILE_MB` (20) | Status `failed` |
| Ingestor restarts mid-file | That file stays `processing`; click **Retry** on the page. (A queue fixes this later, see below.) |

## Contract with the chat backend

Both services must agree on these. Change them together.

| Item | Value |
|---|---|
| Index | `kb-chunks` |
| Embedding model | `amazon.titan-embed-text-v2:0`, `dimensions=1024`, `normalize=true` |
| Vector field | `embedding` (`knn_vector`, faiss HNSW, `innerproduct`) |
| Text field | `text` |
| Metadata | `doc_id`, `tenant_id`, `file_name`, `s3_key`, `chunk_index`, `page`, `indexed_at` |

A search is: embed the question the same way → `knn` query on `embedding` → use `text`, `file_name` and `page` of the top hits.

## Next steps

| Feature | Where |
|---|---|
| Chat answers from these documents | Chat backend: `genai/retriever.py` + `services/chat_service.py` |
| No lost work on restarts or bursts | S3 event → SQS queue → a worker that calls `pipeline.run()` |
| Delete a document's chunks | `DELETE /api/v1/documents/{doc_id}` + `VectorStore.delete_document()` |
| DOCX, scanned PDFs | `pipeline/loader.py` (python-docx; Amazon Textract for OCR) |
| Multi-tenancy | `TENANT_ID` in `pipeline/pipeline.py` comes from the request; filter searches on `tenant_id` |
| Docker | `ingestor/Dockerfile` |
