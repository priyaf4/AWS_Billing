# tests/

Automated tests, run with `pytest`. None of them call AWS, so they're free, fast and repeatable (CI-friendly).

| File | What it checks |
|---|---|
| `test_chunker.py` | Chunk sizes, overlap, natural break points, page numbers, whitespace clean-up |
| `test_pipeline.py` | File name / id rules (re-upload → same id), key validation, status flow `processing → ready`, chunk metadata, failure messages |
| `test_api.py` | Endpoints and status codes, background task triggered, newest-first listing, 404 / 503 |

`test_pipeline.py` builds a real `IngestionPipeline` with fake S3, embedder, OpenSearch and DynamoDB objects.
`test_api.py` replaces the pipeline and repository via `app.dependency_overrides`.
