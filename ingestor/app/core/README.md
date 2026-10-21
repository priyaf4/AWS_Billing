# app/core/

Shared basics used by every layer.

| File | Purpose |
|---|---|
| `config.py` | `Settings`: reads env vars / `.env`. `get_settings()` returns one cached copy. |
| `aws.py` | `make_session()`: one boto3 session (with the ingestor's keys) shared by every AWS client |

## Settings

| Env var | Default | Meaning |
|---|---|---|
| `AWS_REGION` | `ap-southeast-2` | Region of every AWS resource |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | empty → default AWS credential chain | Keys of `rag-ingestor-user` |
| `S3_BUCKET_NAME` | required | Upload bucket |
| `S3_UPLOAD_PREFIX` | `uploads/` | Only files under this prefix are accepted |
| `MAX_FILE_MB` | `20` | Larger files fail |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | `1000`, `150` | Chunk length and shared characters, see `pipeline/README.md` |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | `amazon.titan-embed-text-v2:0`, `1024` | Must match the chat backend |
| `EMBEDDING_CONCURRENCY` | `8` | Parallel Titan calls per file |
| `OPENSEARCH_ENDPOINT` | required | Domain URL |
| `OPENSEARCH_INDEX` | `kb-chunks` | Must match the chat backend |
| `DOCUMENTS_TABLE_NAME` | `documents` | Status table |

Changing `CHUNK_SIZE`, `CHUNK_OVERLAP` or the embedding settings only affects files ingested afterwards. Re-index files to apply it.
