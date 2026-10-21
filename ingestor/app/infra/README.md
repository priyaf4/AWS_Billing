# app/infra/

Code that talks to **AWS services**. Each file wraps one service, so nothing else needs to know its API.

| File | Service | Purpose |
|---|---|---|
| `s3.py` | S3 | `FileStore.read(key)`: download an uploaded file (refuses files over `MAX_FILE_MB`) |
| `vector_store.py` | OpenSearch | `ensure_index()` creates `kb-chunks` on first use; `replace_document_chunks()` writes chunks + vectors |
| `documents_repo.py` | DynamoDB | `save`, `get`, `list_all` for each file's status |

## OpenSearch index `kb-chunks`

Created automatically by `ensure_index()` with the layout in `index_body()`:
- `embedding`: the vector (`knn_vector`, 1024 dims, faiss HNSW, inner product). Vectors are normalized, so this equals cosine similarity.
- `text` plus metadata: `doc_id`, `tenant_id`, `file_name`, `s3_key`, `chunk_index`, `page`, `indexed_at`.
- 1 shard, 0 replicas, which suits the single-node domain. Raise replicas when the domain has more nodes.

Each chunk's id is `<doc_id>-<chunk_index>`. Re-ingesting a file overwrites those ids in place, then deletes any
leftover chunks if the new version is shorter, so search never sees the document missing mid-update.

Requests are signed with the ingestor's AWS keys (`AWSV4SignerAuth`). Inside OpenSearch, that IAM user is mapped
to the `rag_ingestor` role, which only allows the `kb-chunks*` indices.

## DynamoDB table `documents`

One item per file, partition key `PK = "DOC#<doc_id>"`:

| Attribute | Example |
|---|---|
| `doc_id`, `file_name`, `s3_key` | `17974f…`, `Product_Service_Catalog_Rate_Guide.pdf`, `uploads/1792…pdf` |
| `status` | `pending` / `processing` / `ready` / `failed` |
| `chunk_count`, `page_count` | `11`, `6` (when ready) |
| `error` | Reason when failed |
| `updated_at` | ISO timestamp |
