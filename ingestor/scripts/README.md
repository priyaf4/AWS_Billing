# scripts/

One-off admin and diagnostic scripts. They aren't part of the running service.
Run them with a venv that has `boto3` (the ingestor's or the backend's).

| Script | Run with | What it does |
|---|---|---|
| `setup_opensearch_role.py` | OpenSearch **master** user keys (default: `backend/.env`) | Creates the `rag_ingestor` OpenSearch role (only `kb-chunks*`) and maps `rag-ingestor-user` to it. Safe to re-run. |
| `check_access.py` | Ingestor keys (default: `ingestor/.env`) | Confirms S3 read, Titan embeddings, OpenSearch role and DynamoDB access. Read-only except one tiny embedding call. |

```powershell
cd E:\CrackedGoogle2026\Projects\aws
ingestor\.venv\Scripts\python ingestor\scripts\check_access.py
```

Run `check_access.py` whenever keys, policies or the domain change. Each `[FAIL]` line names the permission to fix.
